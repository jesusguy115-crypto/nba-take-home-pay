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
    cards=[]
    for p in data['players']:
        steps=[s for s in p['steps'] if abs(s['amount'])>=1]
        for mode,w,h in [('portrait',1080,1920),('landscape',1920,1080),('cover',1080,1440)]:
            lines=steps if mode!='cover' else [steps[0]]
            x0=400 if mode=='landscape' else 330; plot=w-x0-100
            peak=max(sum(s['amount'] for s in steps[:i+1]) for i in range(len(steps)))
            scale=plot/max(peak,1); start=270; dy=min(70,(h-470)/(len(lines)+1));y=start
            elements=[f'<rect width="{w}" height="{h}" fill="#111516"/>',f'<text x="64" y="85" font-size="25" fill="#d8bc79">NBA / TAKE HOME · {season}</text>',f'<text x="64" y="155" font-size="48" fill="#f4f1e9">{html.escape(p["name"])} · 工资去向</text>',f'<text x="64" y="205" font-size="26" fill="#a9b1b2">税后约 {p["net"]/10000:,.0f} 万美元</text>']
            running=0
            for s in lines:
                end=running+s['amount'];left=x0+min(running,end)*scale;width=max(2,abs(s['amount'])*scale)
                color='#d8bc79' if s['amount']>=0 else '#ad7970'
                elements += [f'<text x="64" y="{y+23}" font-size="22" fill="#e4e5e1">{html.escape(s["label"])}</text>',f'<rect x="{left}" y="{y}" width="{width}" height="28" fill="{color}"/>',f'<text x="{w-55}" y="{y+48}" text-anchor="end" font-size="22" fill="#e4e5e1">{s["amount"]/10000:+,.2f}</text>']
                running=end;y+=dy
            elements += [f'<text x="64" y="{y+55}" font-size="30" fill="#d8bc79">最终税后估值 {p["net"]/10000:,.2f} 万美元</text>']
            for i,line in enumerate([f'单位：万美元 · 薪资快照 {salary_date}','联盟结算为假设；税款含抵免；非真实税单','不含代言与个人费用；完整口径见配套文字说明']):
                elements.append(f'<text x="64" y="{h-125+i*32}" font-size="22" fill="#a9b1b2">{html.escape(line)}</text>')
            svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="Arial, sans-serif">'+''.join(elements)+'</svg>'
            cards.append((p['name']+' '+{'portrait':'竖屏 9:16','landscape':'横屏 16:9','cover':'封面 3:4'}[mode],svg))
    sections=''.join('<section><h2>'+html.escape(label)+'</h2><button onclick="save(this)">生成PNG图片 / 保存</button><div class="art">'+svg+'</div><div class="preview"></div></section>' for label,svg in cards)
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'''+html.escape(title)+'''</title><style>body{background:#111516;color:#f4f1e9;font-family:system-ui;margin:24px}h1{font-size:28px}section{margin:48px auto;max-width:960px}svg,img{width:100%;height:auto}button{background:#d8bc79;padding:16px;border:0;border-radius:6px;font-size:16px;margin:12px 0}.preview a{color:#d8bc79}</style><h1>'''+html.escape(title)+'''</h1><p>竖屏、横屏与封面素材。点击生成PNG，手机可长按图片保存。</p>'''+sections+'''<script>async function save(b){const section=b.closest('section'),svg=section.querySelector('svg'),box=section.querySelector('.preview');b.disabled=true;try{const raw=new Blob([new XMLSerializer().serializeToString(svg)],{type:'image/svg+xml;charset=utf-8'}),url=URL.createObjectURL(raw),im=new Image();await new Promise((ok,no)=>{im.onload=ok;im.onerror=no;im.src=url});const c=document.createElement('canvas');c.width=svg.width.baseVal.value;c.height=svg.height.baseVal.value;c.getContext('2d').drawImage(im,0,0);URL.revokeObjectURL(url);const blob=await new Promise(ok=>c.toBlob(ok,'image/png'));if(!blob)throw Error('PNG生成失败');if(box.dataset.url)URL.revokeObjectURL(box.dataset.url);const out=URL.createObjectURL(blob);box.dataset.url=out;const img=new Image();img.src=out;img.alt='长按保存图片';const a=document.createElement('a');a.href=out;a.download=section.querySelector('h2').textContent+'.png';a.textContent='下载PNG（手机也可长按下图保存）';box.replaceChildren(a,img);box.scrollIntoView({behavior:'smooth'});}catch(e){box.textContent='图片生成失败，请重试：'+e.message}finally{b.disabled=false}}</script></html>'''
    pagepath=Path(str(dest)+'-studio.html');pagepath.write_text(page,encoding='utf-8')
    return {'breakdown':data,'report':str(report.resolve()),'studio':str(pagepath.resolve())}
