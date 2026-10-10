"""Deterministic salary bridge, difference attribution and portable video cards."""
import html
import json
from pathlib import Path

LABELS = {'federal_income_tax':'联邦所得税','national_employee_payroll':'基础工资税','resident_state_province_tax':'居民州/省税','away_state_tax':'客场州税','residence_state_credit':'居民州抵免','work_state_credit':'工作州抵免','resident_local_tax':'居民地方税','away_local_tax':'客场地方税','resident_local_credit':'地方税抵免','extra_employee_payroll':'其他雇员工资税','foreign_income_tax':'境外所得税','foreign_tax_credit':'境外税收抵免'}

def bridge(row):
    steps=[{'label':'合同税前薪水','amount':row['spotrac_salary_usd']}]
    steps += [{'label':'联盟最终扣减（假设）','amount':-row['cashflow_scenario']['modeled_final_reduction_usd']},
              {'label':'联盟补发（假设）','amount':row.get('extra_settlement_bonus_usd',0)},
              {'label':'杯赛奖金（已纳入）','amount':row.get('extra_cup_bonus_usd',0)}]
    for key,value in row['components_usd'].items():
        steps.append({'label':LABELS.get(key,key),'amount':-value})
    residual=round(row['estimated_net_usd']-sum(x['amount'] for x in steps),2)
    if abs(residual) > 0.25:
        raise ValueError('工资分解未对平，请核查计算字段，不能生成误导图表')
    if residual: steps.append({'label':'逐项取整差','amount':residual})
    return steps

def breakdown(rows):
    ledgers=[{'player':r['player'],'steps':bridge(r),'net':r['estimated_net_usd']} for r in rows]
    result={'players':ledgers,'note':'会计差额分解，不是换队因果模拟；税款已反映结算工资情景，10%暂扣不重复扣。'}
    if len(rows)==2:
        a,b=ledgers
        labels=list(dict.fromkeys(x['label'] for p in ledgers for x in p['steps']))
        values=[{x['label']:x['amount'] for x in p['steps']} for p in ledgers]
        result['difference']={'direction':a['player']+' 减 '+b['player'],'net_difference':round(a['net']-b['net'],2),'steps':[{'label':k,'amount':round(values[0].get(k,0)-values[1].get(k,0),2)} for k in labels]}
    return result

def write_pack(rows, destination, season, salary_date):
    from player_names import name_registry
    names={str(r['player_id']):r.get('chinese_name') or r['english_name'] for r in name_registry()['players']}
    data=breakdown(rows)
    for item,row in zip(data['players'],rows):item['name']=names.get(str(row['player_id']),row['player'])
    dest=Path(destination).with_suffix('')
    title='、'.join(p['name'] for p in data['players'])+f' {season}赛季薪水解析'
    md=['# '+title,'','金额单位：万美元。正数增加税后收入，负数减少税后收入。','']
    if 'difference' in data:
        md += ['## 差距拆解（第一人减第二人）','','| 项目 | 对税后差距的贡献 |','|---|---:|']
        md += [f"| {s['label']} | {s['amount']/10000:+,.2f} |" for s in data['difference']['steps'] if s['amount']]
        md += [f"| 最终税后差距 | {data['difference']['net_difference']/10000:+,.2f} |",'',data['note'],'']
    for p in data['players']:
        md+=['## '+p['name'],'','| 项目 | 金额 |','|---|---:|']+[f"| {s['label']} | {s['amount']/10000:+,.2f} |" for s in p['steps'] if s['amount']]+[f"| 税后估值 | {p['net']/10000:,.2f} |",'']
    first=data['players'][0]
    spoken=f"{season}赛季，{first['name']}的税后合同收入估计约{first['net']/10000:,.0f}万美元。"
    if len(rows)==2:
        second=data['players'][1]; gap=data['difference']['net_difference'];spoken+=f"{second['name']}约{second['net']/10000:,.0f}万美元，前者{'多' if gap>=0 else '少'}约{abs(gap)/10000:,.0f}万美元。"
    spoken+='合同工资要经过联盟结算，再扣联邦税、工资税和适用的州及地方税，抵免会减少重复税负。这是基于公开数据的估算，实际申报和结算可能不同，也不包含代言收入。'
    notes=f'薪资快照 {salary_date}；联盟最终扣减按查询假设；非实际到账；不含经纪费等个人扣款。'
    md+=['## 约30秒口播（时长随语速变化）','',spoken,'','## 素材说明','',notes,'','各人申报情景：'+'；'.join(r['player']+' '+r['filing_scenario']['status'] for r in rows),'','来源：'+'；'.join(r['sources']['salary'] for r in rows)]
    report=Path(str(dest)+'-story.md');report.write_text('\n'.join(md),encoding='utf-8')
    # SVG text is escaped; all assets are local. Waterfalls preserve the cumulative balance.
    from render_chart import chart_data
    visual=chart_data({'results':rows,'season':season})['rows']
    cards=[]
    for p,r,v in zip(data['players'],rows,visual):
        all_steps=[(x['label'],x['amount']) for x in p['steps']]
        scenes=[('合同收入与最终结果', [('合同税前薪水',r['spotrac_salary_usd']),('最终税后估值',p['net'])])]
        nonzero=[x for x in all_steps[1:] if x[1] != 0]
        for offset in range(0,len(nonzero),5):
            scenes.append(('工资扣减与抵免明细',nonzero[offset:offset+5]))
        scenes.append(('汇总核对', [('合同税前薪水',r['spotrac_salary_usd']),('全部增减合计',p['net']-r['spotrac_salary_usd']),('最终税后估值',p['net'])]))
        for scene_index,(scene_title,values) in enumerate(scenes):
            e=html.escape
            parts=['<rect width="1920" height="1080" fill="#101416"/>', '<rect x="64" y="64" width="6" height="48" fill="#d8bc79"/>']
            def text(x,y,value,size=28,color='#f3f0e7'):
                parts.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}">{e(str(value))}</text>')
            text(90,100,'COURTSIDE / 薪水解析',28,'#d8bc79')
            text(1390,100,season+'赛季 · 合同收入',26,'#abb3b4')
            parts.append('<path d="M64 140H1856" stroke="#343c3e"/>')
            if v['logo']:parts.append(f'<image href="{v["logo"]}" x="50" y="205" width="670" height="640" opacity=".13"/>')
            if v['portrait']:parts.append(f'<image href="{v["portrait"]}" x="85" y="255" width="620" height="570"/>')
            text(90,215,p['name'],54)
            text(92,875,v['team'],28,'#abb3b4')
            text(800,237,scene_title,30,'#abb3b4')
            text(790,370,f'{p["net"]/10000:,.0f}',112,'#d8bc79');text(1190,365,'万美元',30,'#d8bc79')
            maximum=r['spotrac_salary_usd']
            for i,(label,value) in enumerate(values):
                y=455+i*85;text(800,y,label,27,'#abb3b4');text(1530,y,f'{value/10000:+,.2f}',32)
                parts.append(f'<rect x="800" y="{y+25}" width="980" height="12" rx="6" fill="#293134"/><rect x="800" y="{y+25}" width="{max(3,abs(value)/maximum*980)}" height="12" rx="6" fill="{"#d8bc79" if value>0 else "#9a7770"}"/>')
            text(800,925,f'单位：万美元 · 第{scene_index+1}/{len(scenes)}幕 · 零额项目见配套明细',24,'#abb3b4')
            parts.append('<path d="M64 970H1856" stroke="#343c3e"/>')
            text(64,1020,f'薪资快照 {salary_date} · Spotrac / 头像 ESPN',23,'#abb3b4')
            text(880,1020,f'结算扣减假设 {r["escrow_scenario"]["final_reduction_rate"]:.2%} · 非实际到账 · 不含个人费用',23,'#abb3b4')
            svg='<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080" font-family="PingFang SC, Microsoft YaHei, Arial, sans-serif">'+''.join(parts)+'</svg>'
            cards.append((p['name']+' · '+scene_title,svg))
    sections=''.join('<section><h2>'+html.escape(label)+'</h2><button onclick="save(this)">生成PNG图片 / 保存</button><button onclick="video(this)">生成完整分幕视频（无配音）</button><div class="art">'+svg+'</div><div class="preview"></div></section>' for label,svg in cards)
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'''+html.escape(title)+'''</title><style>body{background:#111516;color:#f4f1e9;font-family:system-ui;margin:24px}h1{font-size:28px}section{margin:48px auto;max-width:960px}svg,img{width:100%;height:auto}button{background:#d8bc79;padding:16px;border:0;border-radius:6px;font-size:16px;margin:12px 0}.preview a{color:#d8bc79}</style><h1>'''+html.escape(title)+'''</h1><p>1920×1080 横屏素材与动态视频。点击生成PNG，手机可长按图片保存。</p>'''+sections+'''<script>async function video(b){const box=b.closest('section'),out=box.querySelector('.preview');if(!window.MediaRecorder||!HTMLCanvasElement.prototype.captureStream){out.textContent='当前浏览器不支持视频导出，请使用Chrome或Edge；仍可保存PNG素材。';return}b.disabled=true;try{const svgs=[...document.querySelectorAll('.art svg')],svg=svgs[0],images=[],urls=[];for(const source of svgs){const im=new Image(),u=URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(source)],{type:'image/svg+xml'}));urls.push(u);await new Promise((ok,no)=>{im.onload=ok;im.onerror=no;im.src=u});images.push(im)}const c=document.createElement('canvas');c.width=svg.width.baseVal.value;c.height=svg.height.baseVal.value;const ctx=c.getContext('2d');const stream=c.captureStream(25),mime=['video/webm;codecs=vp9','video/webm;codecs=vp8','video/mp4'].find(x=>MediaRecorder.isTypeSupported(x));if(!mime)throw Error('没有可用的视频编码器');const recorder=new MediaRecorder(stream,{mimeType:mime}),chunks=[];recorder.ondataavailable=e=>chunks.push(e.data);const done=new Promise(ok=>recorder.onstop=ok);recorder.start();const start=performance.now();await new Promise(resolve=>{function frame(t){const f=Math.min(1,(t-start)/(images.length*4000));ctx.fillStyle='#111516';ctx.fillRect(0,0,c.width,c.height);ctx.save();ctx.beginPath();ctx.rect(0,0,c.width,c.height);ctx.clip();const scene=Math.min(images.length-1,Math.floor(f*images.length));ctx.globalAlpha=Math.min(1,((f*images.length)%1)*8+.2);if(f===1)ctx.globalAlpha=1;ctx.drawImage(images[scene],0,0);ctx.restore();b.textContent='视频生成中 '+Math.round(f*100)+'%';if(f<1)requestAnimationFrame(frame);else resolve()}requestAnimationFrame(frame)});recorder.stop();await done;stream.getTracks().forEach(t=>t.stop());urls.forEach(u=>URL.revokeObjectURL(u));const url=URL.createObjectURL(new Blob(chunks,{type:mime})),v=document.createElement('video'),a=document.createElement('a');v.src=url;v.controls=true;v.style.width='100%';a.href=url;a.download='nba-salary.'+(mime.includes('mp4')?'mp4':'webm');a.textContent='下载完整分幕视频（无配音）';out.replaceChildren(a,v)}catch(e){out.textContent='视频生成失败：'+e.message}finally{b.disabled=false;b.textContent='生成完整分幕视频（无配音）'}}async function save(b){const section=b.closest('section'),svg=section.querySelector('svg'),box=section.querySelector('.preview');b.disabled=true;try{const raw=new Blob([new XMLSerializer().serializeToString(svg)],{type:'image/svg+xml;charset=utf-8'}),url=URL.createObjectURL(raw),im=new Image();await new Promise((ok,no)=>{im.onload=ok;im.onerror=no;im.src=url});const c=document.createElement('canvas');c.width=svg.width.baseVal.value;c.height=svg.height.baseVal.value;c.getContext('2d').drawImage(im,0,0);URL.revokeObjectURL(url);const blob=await new Promise(ok=>c.toBlob(ok,'image/png'));if(!blob)throw Error('PNG生成失败');if(box.dataset.url)URL.revokeObjectURL(box.dataset.url);const out=URL.createObjectURL(blob);box.dataset.url=out;const img=new Image();img.src=out;img.alt='长按保存图片';const a=document.createElement('a');a.href=out;a.download=section.querySelector('h2').textContent+'.png';a.textContent='下载PNG（手机也可长按下图保存）';box.replaceChildren(a,img);box.scrollIntoView({behavior:'smooth'});}catch(e){box.textContent='图片生成失败，请重试：'+e.message}finally{b.disabled=false}}</script></html>'''
    pagepath=Path(str(dest)+'-studio.html');pagepath.write_text(page,encoding='utf-8')
    return {'breakdown':data,'report':str(report.resolve()),'studio':str(pagepath.resolve())}
