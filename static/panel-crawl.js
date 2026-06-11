let currentTab='all',appConfig=null;
async function api(p,o){
    o=o||{};
    const headers=Object.assign({'Content-Type':'application/json'},o.headers||{});
    const r=await fetch(p,Object.assign({},o,{headers}));
    let data=null;
    const text=await r.text();
    if(text){try{data=JSON.parse(text)}catch(e){}}
    if(!r.ok){
        const err=new Error((data&&data.msg)||('HTTP '+r.status));
        err.status=r.status;
        throw err;
    }
    return data||{};
}

function showToast(msg,isErr){
    const t=document.getElementById('toast');
    t.textContent=msg;
    t.className='toast'+(isErr?' error':'');
    t.style.display='block';
    setTimeout(()=>{t.style.display='none'},3000);
}

function sourceHeimao(){return(appConfig&&appConfig.heimao&&appConfig.heimao.source_name)||'黑猫投诉'}
function sourceXhs(){return(appConfig&&appConfig.xhs&&appConfig.xhs.source_name)||'小红书'}

function fillAnalysisFields(ai, status){
    ai=ai||{};
    const set=(id,v)=>{const el=document.getElementById(id);if(el&&v!==undefined&&v!==null)el.value=v;};
    const setNum=(id,v,d)=>{const el=document.getElementById(id);if(el)el.value=(v!=null?v:d);};
    set('cfg-ai-provider', ai.provider||'');
    set('cfg-ai-endpoint', ai.endpoint||'');
    set('cfg-ai-endpoint-intl', ai.endpoint_intl||'');
    set('cfg-ai-model', ai.model||'');
    set('cfg-ai-prompt-ver', ai.prompt_version||'');
    set('cfg-ai-key-env', ai.api_key_env||'MINIMAX_API_KEY');
    setNum('cfg-ai-batch', ai.batch_size, 10);
    setNum('cfg-ai-body-max', ai.max_body_chars, 2000);
    setNum('cfg-ai-retries', ai.max_retries, 2);
    setNum('cfg-ai-retry-delay', ai.retry_delay_sec, 2);
    setNum('cfg-ai-temp', ai.temperature, 0.3);
    setNum('cfg-ai-timeout', ai.timeout_sec, 180);
    const mockEl=document.getElementById('cfg-ai-mock');
    if(mockEl)mockEl.checked=!!ai.mock_without_key;
    const mockRel=document.getElementById('cfg-ai-mock-rel');
    if(mockRel)mockRel.value=ai.mock_default_relevance||'medium';
    const sp=document.getElementById('cfg-ai-system-prompt');
    if(sp)sp.value=ai.system_prompt||'';
    const eb=document.getElementById('cfg-ai-extra-body');
    if(eb)eb.value=ai.extra_body?JSON.stringify(ai.extra_body,null,2):'';
    const keyEl=document.getElementById('cfg-ai-key');
    if(keyEl){
        if(ai.api_key&&ai.api_key!=='***已配置***')keyEl.value=ai.api_key;
        else if(ai.api_key==='***已配置***'||(status&&status.has_api_key))keyEl.value='';
        keyEl.placeholder=(ai.api_key==='***已配置***'||(status&&status.has_api_key))?'已配置（留空不修改）':'留空则使用环境变量';
    }
    const st=document.getElementById('cfg-ai-status');
    if(st&&status){
        if(status.mock_mode)st.textContent='当前：Mock 模式（未检测到 API Key）';
        else if(status.has_api_key)st.textContent='当前：已配置 API Key · 模型 '+ (status.model||'');
        else st.textContent='当前：未配置 API Key';
    }
}

async function loadAnalysisConfigPanel(){
    try{
        const d=await api('/api/analysis/config');
        if(!d.ok){showToast(d.msg||'加载大模型配置失败',true);return;}
        fillAnalysisFields(d.analysis,d.status);
    }catch(e){showToast('加载大模型配置失败',true);}
}

function fillConfigForm(c){
    appConfig=c;
    c=c||{};
    const server=c.server||{};
    const chrome=c.chrome||{};
    const paths=c.paths||{};
    const logging=c.logging||{};
    document.getElementById('cfg-server-host').value=server.host||'';
    document.getElementById('cfg-server-port').value=server.port||5000;
    document.getElementById('cfg-chrome-exe').value=chrome.exe_path||'';
    document.getElementById('cfg-chrome-port').value=chrome.cdp_port||9222;
    document.getElementById('cfg-chrome-profile').value=chrome.profile_dir||'';
    document.getElementById('cfg-chrome-startup').value=chrome.startup_url||'';
    document.getElementById('cfg-output-dir').value=paths.output_dir||'';
    document.getElementById('cfg-max-logs').value=logging.max_logs||300;
    const h=c.heimao||{};
    document.getElementById('cfg-h-kw').value=h.default_keyword||'';
    document.getElementById('cfg-h-pages').value=h.default_max_pages||2;
    document.getElementById('cfg-h-source').value=h.source_name||'';
    document.getElementById('cfg-h-base').value=h.base_url||'';
    document.getElementById('cfg-h-search-tpl').value=h.search_url_template||'';
    document.getElementById('cfg-h-search-sel').value=h.search_input_selector||'';
    document.getElementById('cfg-h-link-regex').value=h.link_regex||'';
    document.getElementById('cfg-h-timeout').value=h.page_timeout_ms||30000;
    document.getElementById('cfg-h-detail-min').value=h.detail_wait_min||5;
    document.getElementById('cfg-h-detail-max').value=h.detail_wait_max||8;
    document.getElementById('cfg-h-author-cats').value=JSON.stringify((h.detail&&h.detail.author_cats)||[]);
    const x=c.xhs||{};
    document.getElementById('cfg-x-kw').value=x.default_keyword||'';
    document.getElementById('cfg-x-pages').value=x.default_max_pages||3;
    document.getElementById('cfg-x-source').value=x.source_name||'';
    document.getElementById('cfg-x-search-tpl').value=x.search_url_template||'';
    document.getElementById('cfg-x-note-sel').value=x.note_item_selector||'';
    document.getElementById('cfg-x-link-sel').value=x.link_selector||'';
    document.getElementById('cfg-x-title-sel').value=x.title_selector||'';
    document.getElementById('cfg-x-text-sel').value=x.text_selector||'';
    document.getElementById('cfg-x-scroll-px').value=x.scroll_pixels||1500;
    document.getElementById('cfg-x-scroll-times').value=x.scroll_times_per_page||3;
    const ex=c.export||{};
    document.getElementById('cfg-ex-csv-header').value=ex.csv_header||'';
    document.getElementById('cfg-ex-content-max').value=ex.content_max_len||500;
    document.getElementById('cfg-ex-reply-max').value=ex.reply_max_len||300;
    document.getElementById('cfg-json-raw').value=JSON.stringify(c,null,2);
    const ah=(c.auth&&c.auth.heimao)||{};
    const ax=(c.auth&&c.auth.xhs)||{};
    document.getElementById('cfg-auth-h-file').value=ah.cookies_file||'';
    document.getElementById('cfg-auth-x-file').value=ax.cookies_file||'';
    document.getElementById('cfg-auth-h-cookies').value=ah.cookies_text||(ah.cookies&&ah.cookies.length?JSON.stringify(ah.cookies,null,2):'');
    document.getElementById('cfg-auth-x-cookies').value=ax.cookies_text||(ax.cookies&&ax.cookies.length?JSON.stringify(ax.cookies,null,2):'');
    document.getElementById('cfg-auth-h-profile').checked=!!ah.use_profile_only;
    document.getElementById('cfg-auth-x-profile').checked=!!ax.use_profile_only;
    document.getElementById('cfg-auth-h-require').checked=!!ah.require_login;
    document.getElementById('cfg-auth-x-require').checked=!!ax.require_login;
    document.getElementById('cfg-auth-h-wait').value=ah.wait_timeout_sec!=null?ah.wait_timeout_sec:300;
    document.getElementById('cfg-auth-x-wait').value=ax.wait_timeout_sec!=null?ax.wait_timeout_sec:300;
    document.getElementById('cfg-auth-poll').value=ah.poll_interval_sec!=null?ah.poll_interval_sec:(ax.poll_interval_sec!=null?ax.poll_interval_sec:3);
    document.getElementById('cfg-auth-auto-export').checked=ah.auto_export_after_login!==false&&ax.auto_export_after_login!==false;
    document.getElementById('cfg-auth-x-probe-len').value=ax.detail_probe_min_content_len!=null?ax.detail_probe_min_content_len:20;
    fillAnalysisFields(c.analysis||{}, null);
    applyConfigToForms();
    refreshAuthStatus();
}

function collectConfigFromForm(){
    let base;
    try{
        base=JSON.parse(document.getElementById('cfg-json-raw').value||'{}');
    }catch(e){
        throw new Error('JSON 高级区格式无效');
    }
    const merge=(t,v)=>{if(!base[t])base[t]={};Object.assign(base[t],v)};
    merge('server',{host:document.getElementById('cfg-server-host').value.trim(),port:+document.getElementById('cfg-server-port').value});
    merge('chrome',{
        exe_path:document.getElementById('cfg-chrome-exe').value.trim(),
        cdp_port:+document.getElementById('cfg-chrome-port').value,
        profile_dir:document.getElementById('cfg-chrome-profile').value.trim(),
        startup_url:document.getElementById('cfg-chrome-startup').value.trim()
    });
    merge('paths',{output_dir:document.getElementById('cfg-output-dir').value.trim()});
    merge('logging',{max_logs:+document.getElementById('cfg-max-logs').value});
    let authorCats=[];
    try{authorCats=JSON.parse(document.getElementById('cfg-h-author-cats').value||'[]')}catch(e){throw new Error('作者昵称列表须为 JSON 数组')}
    merge('heimao',{
        default_keyword:document.getElementById('cfg-h-kw').value.trim(),
        default_max_pages:+document.getElementById('cfg-h-pages').value,
        source_name:document.getElementById('cfg-h-source').value.trim(),
        base_url:document.getElementById('cfg-h-base').value.trim(),
        search_url_template:document.getElementById('cfg-h-search-tpl').value.trim(),
        search_input_selector:document.getElementById('cfg-h-search-sel').value.trim(),
        link_regex:document.getElementById('cfg-h-link-regex').value.trim(),
        page_timeout_ms:+document.getElementById('cfg-h-timeout').value,
        detail_wait_min:+document.getElementById('cfg-h-detail-min').value,
        detail_wait_max:+document.getElementById('cfg-h-detail-max').value
    });
    if(!base.heimao.detail)base.heimao.detail={};
    base.heimao.detail.author_cats=authorCats;
    merge('xhs',{
        default_keyword:document.getElementById('cfg-x-kw').value.trim(),
        default_max_pages:+document.getElementById('cfg-x-pages').value,
        source_name:document.getElementById('cfg-x-source').value.trim(),
        search_url_template:document.getElementById('cfg-x-search-tpl').value.trim(),
        note_item_selector:document.getElementById('cfg-x-note-sel').value.trim(),
        link_selector:document.getElementById('cfg-x-link-sel').value.trim(),
        title_selector:document.getElementById('cfg-x-title-sel').value.trim(),
        text_selector:document.getElementById('cfg-x-text-sel').value.trim(),
        scroll_pixels:+document.getElementById('cfg-x-scroll-px').value,
        scroll_times_per_page:+document.getElementById('cfg-x-scroll-times').value
    });
    merge('export',{
        csv_header:document.getElementById('cfg-ex-csv-header').value.trim(),
        content_max_len:+document.getElementById('cfg-ex-content-max').value,
        reply_max_len:+document.getElementById('cfg-ex-reply-max').value
    });
    const aiKey=document.getElementById('cfg-ai-key').value.trim();
    let extraBody=undefined;
    const extraRaw=document.getElementById('cfg-ai-extra-body').value.trim();
    if(extraRaw){
        try{extraBody=JSON.parse(extraRaw);}catch(e){throw new Error('extra_body 须为合法 JSON');}
    }
    const prevAi=(base.analysis&&typeof base.analysis==='object')?{...base.analysis}:{};
    base.analysis={
        ...prevAi,
        provider:document.getElementById('cfg-ai-provider').value.trim(),
        endpoint:document.getElementById('cfg-ai-endpoint').value.trim(),
        endpoint_intl:document.getElementById('cfg-ai-endpoint-intl').value.trim(),
        model:document.getElementById('cfg-ai-model').value.trim(),
        prompt_version:document.getElementById('cfg-ai-prompt-ver').value.trim(),
        api_key_env:document.getElementById('cfg-ai-key-env').value.trim()||'MINIMAX_API_KEY',
        batch_size:+document.getElementById('cfg-ai-batch').value,
        max_body_chars:+document.getElementById('cfg-ai-body-max').value,
        max_retries:+document.getElementById('cfg-ai-retries').value,
        retry_delay_sec:+document.getElementById('cfg-ai-retry-delay').value,
        temperature:+document.getElementById('cfg-ai-temp').value,
        timeout_sec:+document.getElementById('cfg-ai-timeout').value,
        mock_without_key:document.getElementById('cfg-ai-mock').checked,
        mock_default_relevance:document.getElementById('cfg-ai-mock-rel').value,
        system_prompt:document.getElementById('cfg-ai-system-prompt').value,
    };
    if(extraBody!==undefined)base.analysis.extra_body=extraBody;
    if(aiKey)base.analysis.api_key=aiKey;
    else if(prevAi.api_key&&prevAi.api_key!=='***已配置***')base.analysis.api_key=prevAi.api_key;
    const pollSec=+document.getElementById('cfg-auth-poll').value;
    const autoExport=document.getElementById('cfg-auth-auto-export').checked;
    merge('auth',{
        heimao:{
            cookies_file:document.getElementById('cfg-auth-h-file').value.trim(),
            cookies_text:document.getElementById('cfg-auth-h-cookies').value.trim(),
            use_profile_only:document.getElementById('cfg-auth-h-profile').checked,
            require_login:document.getElementById('cfg-auth-h-require').checked,
            wait_timeout_sec:+document.getElementById('cfg-auth-h-wait').value,
            poll_interval_sec:pollSec,
            auto_export_after_login:autoExport
        },
        xhs:{
            cookies_file:document.getElementById('cfg-auth-x-file').value.trim(),
            cookies_text:document.getElementById('cfg-auth-x-cookies').value.trim(),
            use_profile_only:document.getElementById('cfg-auth-x-profile').checked,
            require_login:document.getElementById('cfg-auth-x-require').checked,
            wait_timeout_sec:+document.getElementById('cfg-auth-x-wait').value,
            poll_interval_sec:pollSec,
            auto_export_after_login:autoExport,
            detail_probe_min_content_len:+document.getElementById('cfg-auth-x-probe-len').value
        }
    });
    return base;
}

async function reloadConfig(){
    try{
        const c=await api('/api/config');
        fillConfigForm(c);
        await loadAnalysisConfigPanel();
        showToast('配置已加载');
    }catch(e){showToast('加载配置失败',true)}
}

async function saveConfig(){
    try{
        const body=collectConfigFromForm();
        const r=await api('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
        if(!r.ok){showToast(r.msg||'保存失败',true);return}
        await reloadConfig();
        showToast('配置已保存');
    }catch(e){showToast(e.message||'保存失败',true)}
}

function applyConfigToForms(){
    if(!appConfig)return;
    document.getElementById('kw-heimao').value=appConfig.heimao.default_keyword||'';
    document.getElementById('pages-heimao').value=appConfig.heimao.default_max_pages||2;
    document.getElementById('detail-heimao').checked=!!appConfig.heimao.default_fetch_detail;
    document.getElementById('kw-xhs').value=appConfig.xhs.default_keyword||'';
    document.getElementById('pages-xhs').value=appConfig.xhs.default_max_pages||3;
    document.getElementById('detail-xhs').checked=!!appConfig.xhs.default_fetch_detail;
}

function toggleConfig(){
    if(window.App&&App.switchAppTab){App.switchAppTab('system');return;}
    const p=document.getElementById('system-config-panel')||document.getElementById('config-panel');
    if(p)p.style.display=p.style.display==='none'?'block':'none';
}

function switchConfigTab(name,el){
    document.querySelectorAll('.config-tab').forEach(e=>e.classList.remove('active'));
    document.querySelectorAll('.config-section').forEach(e=>e.classList.remove('active'));
    el.classList.add('active');
    document.getElementById('cfg-'+name).classList.add('active');
    if(name==='analysis')loadAnalysisConfigPanel();
}

function renderResults(data){
    const sh=sourceHeimao(),sx=sourceXhs();
    const filtered=currentTab==='all'?data:data.filter(r=>r.source===(currentTab==='heimao'?sh:sx));
    document.getElementById('total').textContent=filtered.length;
    const tbody=document.getElementById('results-body');
    if(!filtered.length){tbody.innerHTML='<tr><td colspan="7" style="text-align:center;padding:40px;color:#64748b">暂无数据</td></tr>';return}
    tbody.innerHTML=filtered.map((r,i)=>{
        const src=r.source===sh?'heimao':'xhs';
        const link=r.link?'<a href="'+r.link+'" target="_blank">查看</a>':'-';
        const content=(r.content||r.demand||'').substring(0,60);
        const st=r.structured&&r.structured.labels;
        const who=(st&&st['投诉对象'])||r.merchant||r.author||'-';
        const title=(st&&st['投诉标题'])||r.title||'-';
        const time=(st&&st['发布时间'])||r.time||'-';
        return'<tr><td>'+(i+1)+'</td><td><span class="source-tag source-'+src+'">'+r.source+'</span></td><td title="'+String(title).replace(/"/g,'&quot;')+'">'+title+'</td><td>'+who+'</td><td>'+time+'</td><td title="'+content.replace(/"/g,'&quot;')+'">'+content+'</td><td>'+link+'</td></tr>';
    }).join('');
}

function renderLogs(logs){
    document.getElementById('logs').innerHTML=logs.map(l=>'<div class="log-line"><span class="log-time">'+l.time+'</span> <span class="log-level '+(l.level||'')+'">['+(l.level||'INFO')+']</span> <span class="log-msg">'+(l.msg||'').replace(/</g,'&lt;')+'</span></div>').join('');
    document.getElementById('logs').scrollTop=99999;
}

function siteLabel(site){return site==='heimao'?'黑猫投诉':site==='xhs'?'小红书':site}

function updateUI(s){
    document.getElementById('dot-browser').className='status-dot'+(s.browser_launched?' active':'');
    document.getElementById('dot-heimao').className='status-dot'+(s.running&&s.running_type==='heimao'?' running':(s.count_heimao?' active':''));
    document.getElementById('dot-xhs').className='status-dot'+(s.running&&s.running_type==='xhs'?' running':(s.count_xhs?' active':''));
    document.getElementById('count-heimao').textContent=s.count_heimao;
    document.getElementById('count-xhs').textContent=s.count_xhs;
    document.getElementById('btn-heimao').disabled=s.running;
    document.getElementById('btn-xhs').disabled=s.running;
    const banner=document.getElementById('login-wait-banner');
    if(s.login_wait){
        const w=s.login_wait;
        const elapsed=w.elapsed_sec!=null?w.elapsed_sec:0;
        const left=Math.max(0,(w.timeout_sec||300)-elapsed);
        banner.style.display='block';
        document.getElementById('login-wait-title').textContent='等待'+siteLabel(w.site)+'登录';
        document.getElementById('login-wait-detail').textContent='（已等待 '+elapsed+' 秒，约 '+left+' 秒后超时）';
        document.getElementById('running-info').textContent='';
    }else{
        banner.style.display='none';
        document.getElementById('running-info').textContent=s.running?('运行中: '+s.running_type):'';
    }
    renderLogs(s.logs||[]);
}

async function poll(){
    try{
        const s=await api('/api/status');updateUI(s);
        const[a,b]=await Promise.all([api('/api/results_heimao'),api('/api/results_xhs')]);
        renderResults([...a,...b]);
    }catch(e){console.error(e)}
}
function startPoll(){}
async function launchChrome(){await api('/api/launch',{method:'POST'});setTimeout(poll,5000)}
async function startHeimao(){
    const h=appConfig&&appConfig.heimao||{};
    await api('/api/crawl_heimao',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
            keyword:document.getElementById('kw-heimao').value||h.default_keyword||'小米',
            max_pages:+document.getElementById('pages-heimao').value||h.default_max_pages||2,
            fetch_detail:document.getElementById('detail-heimao').checked
        })});poll()}
async function startXhs(){
    const x=appConfig&&appConfig.xhs||{};
    await api('/api/crawl_xhs',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
            keyword:document.getElementById('kw-xhs').value||x.default_keyword||'小米',
            max_pages:+document.getElementById('pages-xhs').value||x.default_max_pages||3,
            fetch_detail:document.getElementById('detail-xhs').checked
        })});poll()}
async function stopAll(){await api('/api/stop',{method:'POST'});poll()}
async function clearAll(){await api('/api/clear',{method:'POST'});poll()}
function switchTab(t,el){currentTab=t;document.querySelectorAll('.tab-bar .tab').forEach(e=>e.classList.remove('active'));el.classList.add('active');poll()}
function exportData(s,f){window.open('/api/export_'+s+'?format='+f,'_blank')}
function openReport(fmt){
    if(fmt==='html'){window.open('/api/report/heimao?format=html','_blank');return}
    window.open('/api/report/heimao?format='+fmt+'&download=1','_blank')
}
async function refreshAuthStatus(){
    try{
        const s=await api('/api/auth/status');
        const hSub=s.heimao&&s.heimao.has_weibo_sub?'(含微博SUB)':'(缺微博SUB!)';
        const xSess=s.xhs&&s.xhs.has_xhs_session?'(含web_session)':'(缺会话Cookie!)';
        const t='黑猫 Cookie: '+(s.heimao&&s.heimao.cookie_count||0)+' 条 '+hSub+' | 小红书: '+(s.xhs&&s.xhs.cookie_count||0)+' 条 '+xSess;
        const el=document.getElementById('auth-status-text');
        const badge=document.getElementById('auth-badge');
        if(el)el.textContent=t;
        if(badge)badge.textContent=t;
    }catch(e){}
}
async function authOpenLogin(site){
    await api('/api/auth/open_login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({site})});
    showToast('请在 Chrome 窗口完成登录');
    setTimeout(poll,2000)
}
async function authDiagnose(site){
    await api('/api/auth/diagnose',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({site})});
    showToast('诊断结果见下方日志');
    setTimeout(poll,3000);
}
async function authExport(site){
    await api('/api/auth/export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({site})});
    showToast('正在导出 '+site+' Cookie…');
    setTimeout(()=>{reloadConfig();refreshAuthStatus()},8000)
}
async function authSaveCookies(){
    try{
        for(const site of ['heimao','xhs']){
            const text=document.getElementById('cfg-auth-'+(site==='heimao'?'h':'x')+'-cookies').value.trim();
            if(!text)continue;
            const r=await api('/api/auth/save',{method:'POST',headers:{'Content-Type':'application/json'},
                body:JSON.stringify({site,cookies_text:text})});
            if(!r.ok)throw new Error(r.msg||'保存失败');
        }
        await saveConfig();
        refreshAuthStatus();
        showToast('Cookie 已保存');
    }catch(e){showToast(e.message||'保存失败',true)}
}
