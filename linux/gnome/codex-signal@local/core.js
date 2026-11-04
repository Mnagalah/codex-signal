/* Pure model shared by GJS and Node tests. No process, task or approval actions. */
var API = (() => {
    const colors = {running:'#2963e8', approval:'#ffab2b', input:'#874ad6', completed:'#24a359', failed:'#d4333d', stopped:'#9ea3ad', unknown:'#9ea3ad', syncing:'#9ea3ad'};
    function language(state) { return state && state.uiLanguage === 'zh-CN' ? 0 : 1; }
    function text(copy, state, key, values = {}) {
        const pair=copy[key]; if (!pair) return key;
        return pair[language(state)].replace(/\{(\w+)\}/g, (_, name) => String(values[name] === undefined ? '{'+name+'}' : values[name]));
    }
    function controls(state) { return state.projectControls || state.projects || []; }
    function active(state) { return controls(state).filter(p => p.updatesEnabled !== false); }
    function summary(state, priority) {
        if (state.enabled === false) return null;
        const phases = new Set(active(state).flatMap(p => p.threads.map(c => c.status === 'syncing' ? 'syncing' : state.connected ? c.status : 'unknown')));
        return priority.find(p => phases.has(p)) || (phases.has('syncing') ? 'syncing' : null);
    }
    function menuProjects(state) { return state.enabled === false || state.compactMenuBar ? [] : (state.projects || []).filter(p => !p.syncing && p.updatesEnabled !== false); }
    function projectName(copy,state,p) { return p.kind === 'chat-bucket' ? text(copy,state,'chatBucket') : p.kind === 'pending' ? text(copy,state,'pendingProject') : p.name; }
    function elapsed(copy,state,since,now) {
        const n=Math.max(0,Math.floor(now-since));
        return n<60 ? text(copy,state,'seconds',{n}) : n<3600 ? text(copy,state,'minutes',{n:Math.floor(n/60)}) : text(copy,state,'hoursMinutes',{h:Math.floor(n/3600),m:Math.floor(n%3600/60)});
    }
    function rows(state,projectId) {
        const selected=projectId === 'global-control' ? controls(state) : controls(state).filter(p=>p.id===projectId);
        const result=[];
        for (const p of selected) {
            if (projectId === 'global-control') result.push({kind:'project',key:'project:'+p.id,project:p});
            if (state.enabled !== false && p.updatesEnabled !== false && (projectId !== 'global-control' || state.compactMenuBar))
                p.threads.forEach(c=>result.push({kind:'chat',key:'chat:'+c.id,project:p,chat:c}));
        }
        return result;
    }
    function color(phase,globalEntry=false) { return phase && !(globalEntry && phase==='syncing') ? colors[phase] || colors.unknown : '#000000'; }
    function rgb(hex) { return [1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)); }
    function foreground(hex) { const c=rgb(hex).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}); return .2126*c[0]+.7152*c[1]+.0722*c[2]>Math.sqrt(.0525)-.05 ? '#000000' : '#ffffff'; }
    function validState(value) {
        return value && value.kind==='state' && typeof value.connected==='boolean' && Array.isArray(value.projects) && [...value.projects,...controls(value)].every(p=>typeof p.id==='string' && typeof p.name==='string' && Array.isArray(p.threads) && p.threads.every(c=>typeof c.id==='string' && typeof c.title==='string' && Number.isInteger(c.index) && c.index>0 && typeof c.since==='number' && typeof c.status==='string'));
    }
    function noticeAllowed(notice,state) {
        const phases=state.notificationStates || ['running','approval','input','completed','failed','stopped'];
        const p=controls(state).find(p=>p.id===notice.project.id);
        return state.enabled!==false && (!p || p.updatesEnabled!==false) && (notice.source!=='automatic' || phases.includes(notice.chat.status));
    }
    function validNotice(n) {return n && typeof n.id==='string' && n.project && typeof n.project.id==='string' && typeof n.project.name==='string' && n.chat && typeof n.chat.id==='string' && typeof n.chat.title==='string' && Number.isInteger(n.chat.index) && colors[n.chat.status];}
    function spring(value,velocity,target,dt,response,damping) {
        // Exact underdamped spring step. Preserve position AND velocity on reversal.
        const w=2*Math.PI/response,z=Math.min(.999,damping),d=w*Math.sqrt(1-z*z),x=value-target,e=Math.exp(-z*w*dt),co=Math.cos(d*dt),si=Math.sin(d*dt),b=(velocity+z*w*x)/d;
        return {value:target+e*(x*co+b*si),velocity:e*((-z*w*x+d*b)*co+(-z*w*b-d*x)*si)};
    }
    function safeEmoji(value) {return typeof value==='string' && value.length>0 && value.length<=64 && !/[\s\u0000-\u001f]/u.test(value);}
    return {colors,language,text,controls,active,summary,menuProjects,projectName,elapsed,rows,color,rgb,foreground,validState,noticeAllowed,validNotice,spring,safeEmoji};
})();
if (typeof module !== 'undefined') module.exports=API;
