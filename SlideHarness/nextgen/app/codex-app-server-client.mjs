import { spawn } from 'node:child_process';
import { EventEmitter } from 'node:events';
import { createInterface } from 'node:readline';
import path from 'node:path';

export class CodexAppServerClient extends EventEmitter {
  constructor({ codexBin = process.env.CODEX_BIN || 'codex', cwd = process.cwd() } = {}) {
    super();
    this.codexBin = codexBin;
    this.cwd = cwd;
    this.proc = null;
    this.seq = 1;
    this.pending = new Map();
    this.serverRequests = new Map();
    this.initialized = false;
    this.starting = null;
  }

  get available() {
    return Boolean(this.proc && !this.proc.killed && this.initialized);
  }

  async start() {
    if (this.available) return;
    if (this.starting) return this.starting;
    this.starting = new Promise((resolve, reject) => {
      let settled = false;
      const proc = spawn(this.codexBin, ['app-server', '--listen', 'stdio://'], {
        cwd: this.cwd,
        stdio: ['pipe', 'pipe', 'pipe'],
        env: process.env,
      });
      this.proc = proc;

      proc.on('error', (err) => {
        this.emit('status', { type: 'codex_status', status: 'unavailable', error: err.message });
        if (!settled) {
          settled = true;
          reject(err);
        }
      });
      proc.on('exit', (code, signal) => {
        this.initialized = false;
        this.emit('status', { type: 'codex_status', status: 'stopped', code, signal });
        for (const [, p] of this.pending) p.reject(new Error(`codex app-server exited (${code ?? signal})`));
        this.pending.clear();
      });

      const out = createInterface({ input: proc.stdout });
      out.on('line', (line) => this.#onLine(line));
      const err = createInterface({ input: proc.stderr });
      err.on('line', (line) => this.emit('stderr', { type: 'codex_stderr', line }));

      this.request('initialize', {
        clientInfo: {
          name: 'ppt_slide_builder_local',
          title: 'PPT Slide Builder Local',
          version: '0.1.0',
        },
      }, { allowBeforeInit: true, timeoutMs: 15000 })
        .then((result) => {
          this.notify('initialized', {});
          this.initialized = true;
          this.emit('status', { type: 'codex_status', status: 'ready', result });
          if (!settled) {
            settled = true;
            resolve();
          }
        })
        .catch((e) => {
          if (!settled) {
            settled = true;
            reject(e);
          }
        });
    }).finally(() => { this.starting = null; });
    return this.starting;
  }

  async ensureStarted() {
    if (!this.available) await this.start();
  }

  #write(message) {
    if (!this.proc?.stdin?.writable) throw new Error('Codex app-server is not writable');
    this.proc.stdin.write(`${JSON.stringify(message)}\n`);
  }

  request(method, params = {}, { allowBeforeInit = false, timeoutMs = 120000 } = {}) {
    if (!allowBeforeInit && !this.initialized) return Promise.reject(new Error('Codex app-server not initialized'));
    const id = this.seq++;
    const msg = { method, id, params };
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Codex request timed out: ${method}`));
      }, timeoutMs);
      this.pending.set(id, {
        method,
        resolve: (value) => { clearTimeout(timer); resolve(value); },
        reject: (err) => { clearTimeout(timer); reject(err); },
      });
      try {
        this.#write(msg);
      } catch (e) {
        clearTimeout(timer);
        this.pending.delete(id);
        reject(e);
      }
    });
  }

  notify(method, params = {}) {
    this.#write({ method, params });
  }

  #onLine(line) {
    let msg;
    try {
      msg = JSON.parse(line);
    } catch {
      this.emit('protocol_error', { type: 'protocol_error', line });
      return;
    }

    if (Object.prototype.hasOwnProperty.call(msg, 'id') && !msg.method) {
      const pending = this.pending.get(msg.id);
      if (pending) {
        this.pending.delete(msg.id);
        if (msg.error) pending.reject(new Error(msg.error.message || JSON.stringify(msg.error)));
        else pending.resolve(msg.result);
      }
      return;
    }

    if (msg.method && Object.prototype.hasOwnProperty.call(msg, 'id')) {
      this.serverRequests.set(msg.id, msg);
      this.emit('server_request', {
        type: 'server_request',
        requestId: msg.id,
        method: msg.method,
        params: msg.params || {},
      });
      return;
    }

    if (msg.method) {
      this.emit('notification', { type: 'codex_notification', method: msg.method, params: msg.params || {} });
      if (msg.method === 'item/agentMessage/delta') {
        this.emit('agent_delta', { type: 'agent_delta', ...msg.params });
      }
      if (msg.method === 'item/started') {
        this.emit('item_started', { type: 'item_started', ...msg.params });
      }
      if (msg.method === 'item/completed') {
        this.emit('item_completed', { type: 'item_completed', ...msg.params });
      }
      if (msg.method === 'turn/completed') {
        this.emit('turn_completed', { type: 'turn_completed', ...msg.params });
      }
      return;
    }

    this.emit('protocol_message', { type: 'protocol_message', message: msg });
  }

  respondToServerRequest(requestId, result) {
    const numeric = Number(requestId);
    const key = this.serverRequests.has(requestId)
      ? requestId
      : (!Number.isNaN(numeric) && this.serverRequests.has(numeric) ? numeric : null);
    if (key === null) throw new Error(`Unknown server request ${requestId}`);
    this.#write({ id: key, result });
    this.serverRequests.delete(key);
  }

  async accountRead() {
    await this.ensureStarted();
    return this.request('account/read', { refreshToken: false });
  }

  async modelList() {
    await this.ensureStarted();
    return this.request('model/list', { limit: 50, includeHidden: false });
  }

  async modelProviderCapabilitiesRead() {
    await this.ensureStarted();
    return this.request('modelProvider/capabilities/read', {});
  }

  async loginChatGPT() {
    await this.ensureStarted();
    return this.request('account/login/start', {
      type: 'chatgpt',
      useHostedLoginSuccessPage: true,
      appBrand: 'chatgpt',
    });
  }

  async loginDeviceCode() {
    await this.ensureStarted();
    return this.request('account/login/start', { type: 'chatgptDeviceCode' });
  }

  async logout() {
    await this.ensureStarted();
    return this.request('account/logout', {});
  }

  async startThread({ cwd, model = 'gpt-5.6-sol', serviceName = 'ppt_slide_builder_local' }) {
    await this.ensureStarted();
    return this.request('thread/start', {
      model,
      cwd: path.resolve(cwd),
      approvalPolicy: 'on-request',
      sandbox: 'workspace-write',
      serviceName,
    });
  }

  async resumeThread({ threadId }) {
    await this.ensureStarted();
    return this.request('thread/resume', { threadId });
  }

  async startTurn({
    threadId,
    cwd,
    text,
    skillPath,
    skillName = 'slide-builder',
    model = 'gpt-5.6-sol',
    effort = 'high',
    approvalPolicy = 'on-request',
    additionalInput = [],
    outputSchema = null,
    sandboxPolicy = null,
  }) {
    await this.ensureStarted();
    const input = [{ type: 'text', text: skillPath ? `$${skillName} ${text}` : text }];
    if (skillPath) input.push({ type: 'skill', name: skillName, path: path.resolve(skillPath) });
    input.push(...additionalInput);
    const params = {
      threadId,
      input,
      cwd: path.resolve(cwd),
      approvalPolicy,
      sandboxPolicy: sandboxPolicy || {
        type: 'workspaceWrite',
        writableRoots: [path.resolve(cwd)],
        networkAccess: false,
      },
      model,
      effort,
      summary: 'concise',
    };
    if (outputSchema) params.outputSchema = outputSchema;
    return this.request('turn/start', params);
  }

  async interruptTurn({ threadId, turnId }) {
    await this.ensureStarted();
    return this.request('turn/interrupt', { threadId, turnId });
  }
}
