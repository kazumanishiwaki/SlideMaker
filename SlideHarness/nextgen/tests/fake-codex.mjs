#!/usr/bin/env node
import readline from 'node:readline';
const rl = readline.createInterface({input: process.stdin});
const send = (x) => process.stdout.write(JSON.stringify(x)+'\n');
let approvalId = 900;
rl.on('line', line => {
  let m; try { m=JSON.parse(line) } catch { return; }
  if (m.method === 'initialize') return send({id:m.id,result:{serverInfo:{name:'fake-codex',version:'0.0.1'}}});
  if (m.method === 'initialized') return;
  if (m.method === 'account/read') return send({id:m.id,result:{account:{type:'chatgpt',planType:'pro'},requiresOpenaiAuth:true}});
  if (m.method === 'account/login/start') return send({id:m.id,result:{type:m.params.type,loginId:'login_fake',authUrl:'https://example.invalid/login',verificationUrl:'https://example.invalid/device',userCode:'ABCD-EFGH'}});
  if (m.method === 'account/logout') return send({id:m.id,result:{}});
  if (m.method === 'model/list') return send({id:m.id,result:{data:[{id:'gpt-5.6-sol',model:'gpt-5.6-sol',displayName:'GPT-5.6 Sol'}]}});
  if (m.method === 'modelProvider/capabilities/read') return send({id:m.id,result:{imageGeneration:true,namespaceTools:true,webSearch:true}});
  if (m.method === 'thread/start') return send({id:m.id,result:{thread:{id:'thr_fake'}}});
  if (m.method === 'thread/resume') return send({id:m.id,result:{thread:{id:m.params.threadId}}});
  if (m.method === 'turn/start') {
    send({id:m.id,result:{turn:{id:'turn_fake',status:'inProgress'}}});
    setTimeout(()=>send({method:'item/agentMessage/delta',params:{threadId:m.params.threadId,turnId:'turn_fake',delta:'mock delta'}}),10);
    setTimeout(()=>send({method:'item/completed',params:{threadId:m.params.threadId,turnId:'turn_fake',completedAtMs:Date.now(),item:{id:'item_fake',type:'agentMessage',text:'done'}}}),15);
    setTimeout(()=>send({id:approvalId,method:'item/commandExecution/requestApproval',params:{threadId:m.params.threadId,turnId:'turn_fake',command:['python3','-m','slideharness_next.cli','--help']}}),20);
    setTimeout(()=>send({method:'turn/completed',params:{threadId:m.params.threadId,turn:{id:'turn_fake',status:'completed'}}}),40);
    return;
  }
  if (Object.prototype.hasOwnProperty.call(m,'id') && !m.method) return;
  if (m.method === 'turn/interrupt') return send({id:m.id,result:{}});
  send({id:m.id,error:{code:-32601,message:`unknown ${m.method}`}});
});
