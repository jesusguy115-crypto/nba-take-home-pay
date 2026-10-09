"""Chinese aliases for offline matching; ambiguous surnames never force a match."""
import re
import unicodedata
from duty_days import TEAMS

ALIASES = {
 '库里':'Stephen Curry','斯蒂芬库里':'Stephen Curry','萌神':'Stephen Curry',
 '赛斯库里':'Seth Curry','小库里':'Seth Curry','爱德华兹':'Anthony Edwards','华子':'Anthony Edwards','安东尼爱德华兹':'Anthony Edwards',
 '詹姆斯':'LeBron James','勒布朗':'LeBron James','勒布朗詹姆斯':'LeBron James','老詹':'LeBron James','布朗尼':'Bronny James',
 '杜兰特':'Kevin Durant','东契奇':'Luka Doncic','约基奇':'Nikola Jokic','约老师':'Nikola Jokic',
 '字母哥':'Giannis Antetokounmpo','扬尼斯':'Giannis Antetokounmpo','文班亚马':'Victor Wembanyama','文班':'Victor Wembanyama',
 '拉梅洛鲍尔':'LaMelo Ball','拉梅洛':'LaMelo Ball','三球':'LaMelo Ball','朗佐鲍尔':'Lonzo Ball','大球':'Lonzo Ball',
 '哈登':'James Harden','詹姆斯哈登':'James Harden','加兰':'Darius Garland','戴维斯':'Anthony Davis','浓眉':'Anthony Davis',
 '恩比德':'Joel Embiid','塔图姆':'Jayson Tatum','杰伦布朗':'Jaylen Brown','巴特勒':'Jimmy Butler','布克':'Devin Booker',
 '戈贝尔':'Rudy Gobert','康利':'Mike Conley','唐斯':'Karl-Anthony Towns','亚历山大':'Shai Gilgeous-Alexander','谢伊':'Shai Gilgeous-Alexander',
 '米切尔':'Donovan Mitchell','利拉德':'Damian Lillard','欧文':'Kyrie Irving','杨瀚森':'Yang Hansen','杨翰森':'Yang Hansen','小杨':'Yang Hansen',
 '伦纳德':'Kawhi Leonard','莱昂纳德':'Kawhi Leonard','小卡':'Kawhi Leonard','保罗乔治':'Paul George','乔治':'Paul George',
 '莫兰特':'Ja Morant','贾莫兰特':'Ja Morant','锡安':'Zion Williamson','锡安威廉姆森':'Zion Williamson',
 '特雷杨':'Trae Young','特雷':'Trae Young','哈利伯顿':'Tyrese Haliburton','哈里伯顿':'Tyrese Haliburton',
 '布伦森':'Jalen Brunson','杰伦布伦森':'Jalen Brunson','马克西':'Tyrese Maxey','马克西姆':'Tyrese Maxey',
 '福克斯':'DeAaron Fox','德阿隆福克斯':'DeAaron Fox','萨博尼斯':'Domantas Sabonis','小萨':'Domantas Sabonis',
 '阿德巴约':'Bam Adebayo','希罗':'Tyler Herro','希尔罗':'Tyler Herro','德罗赞':'DeMar DeRozan','拉文':'Zach LaVine',
 '申京':'Alperen Sengun','申根':'Alperen Sengun','杰伦格林':'Jalen Green','范弗利特':'Fred VanVleet',
 '贾马尔穆雷':'Jamal Murray','贾马尔默里':'Jamal Murray','阿隆戈登':'Aaron Gordon','阿龙戈登':'Aaron Gordon','小波特':'Michael Porter Jr.',
 '德章泰穆雷':'Dejounte Murray','德章泰默里':'Dejounte Murray','英格拉姆':'Brandon Ingram','麦科勒姆':'CJ McCollum',
 '霍勒迪':'Jrue Holiday','朱霍勒迪':'Jrue Holiday','追梦':'Draymond Green','追梦格林':'Draymond Green','德雷蒙德格林':'Draymond Green',
 '克莱':'Klay Thompson','克莱汤普森':'Klay Thompson','汤神':'Klay Thompson','维金斯':'Andrew Wiggins','威金斯':'Andrew Wiggins',
 '里夫斯':'Austin Reaves','拉塞尔':'DAngelo Russell','丹吉洛拉塞尔':'DAngelo Russell','威少':'Russell Westbrook','威斯布鲁克':'Russell Westbrook',
 '保罗':'Chris Paul','克里斯保罗':'Chris Paul','洛瑞':'Kyle Lowry','霍福德':'Al Horford','乐福':'Kevin Love',
 '艾顿':'Deandre Ayton','阿夫迪亚':'Deni Avdija','格兰特':'Jerami Grant','夏普':'Shaedon Sharpe','亨德森':'Scoot Henderson','克林根':'Donovan Clingan',
 '西蒙斯':'Anfernee Simons','安芬尼西蒙斯':'Anfernee Simons','本西蒙斯':'Ben Simmons',
 '坎宁安':'Cade Cunningham','康宁汉姆':'Cade Cunningham','杜伦':'Jalen Duren','艾维':'Jaden Ivey','奥萨尔汤普森':'Ausar Thompson',
 '阿门汤普森':'Amen Thompson','阿门':'Amen Thompson','巴恩斯':'Scottie Barnes','斯科蒂巴恩斯':'Scottie Barnes','巴雷特':'RJ Barrett',
 '奎克利':'Immanuel Quickley','珀尔特尔':'Jakob Poeltl','波尔特尔':'Jakob Poeltl','班凯罗':'Paolo Banchero',
 '小瓦格纳':'Franz Wagner','弗朗茨瓦格纳':'Franz Wagner','大瓦格纳':'Moritz Wagner','萨格斯':'Jalen Suggs','贝恩':'Desmond Bane',
 '小贾伦杰克逊':'Jaren Jackson Jr.','小杰克逊':'Jaren Jackson Jr.','杰伦威廉姆斯':'Jalen Williams','杰伦威廉姆斯雷霆':'Jalen Williams',
 '霍姆格伦':'Chet Holmgren','切特':'Chet Holmgren','哈尔滕施泰因':'Isaiah Hartenstein','多尔特':'Luguentz Dort',
 '马尔卡宁':'Lauri Markkanen','凯斯勒':'Walker Kessler','基昂特乔治':'Keyonte George','科利尔':'Isaiah Collier',
 '波尔津吉斯':'Kristaps Porzingis','怀特':'Derrick White','德里克怀特':'Derrick White','普里查德':'Payton Pritchard',
 '哈特':'Josh Hart','约什哈特':'Josh Hart','阿努诺比':'OG Anunoby','布里奇斯':'Mikal Bridges','米卡尔布里奇斯':'Mikal Bridges','迈尔斯布里奇斯':'Miles Bridges',
 '莫布利':'Evan Mobley','阿伦':'Jarrett Allen','贾勒特阿伦':'Jarrett Allen','斯特鲁斯':'Max Strus','梅里尔':'Sam Merrill',
 '特纳':'Myles Turner','西亚卡姆':'Pascal Siakam','内姆哈德':'Andrew Nembhard','马瑟林':'Bennedict Mathurin',
 '波蒂斯':'Bobby Portis','库兹马':'Kyle Kuzma','米德尔顿':'Khris Middleton','大洛佩兹':'Brook Lopez','布鲁克洛佩兹':'Brook Lopez',
 '普尔':'Jordan Poole','乔丹普尔':'Jordan Poole','麦克丹尼尔斯':'Jaden McDaniels','里德':'Naz Reid','兰德尔':'Julius Randle',
 '库明加':'Jonathan Kuminga','波杰姆斯基':'Brandin Podziemski','穆迪':'Moses Moody','卢尼':'Kevon Looney',
 '祖巴茨':'Ivica Zubac','博格丹':'Bogdan Bogdanovic','邓恩':'Kris Dunn','琼斯':'Derrick Jones Jr.',
 '弗拉格':'Cooper Flagg','库珀弗拉格':'Cooper Flagg','哈珀':'Dylan Harper','迪伦哈珀':'Dylan Harper','贝利':'Ace Bailey','埃奇库姆':'VJ Edgecombe',
 '克尼佩尔':'Kon Knueppel','特雷约翰逊':'Tre Johnson','迪伦布鲁克斯':'Dillon Brooks','狄龙':'Dillon Brooks','伊森':'Tari Eason',
 '小贾巴里史密斯':'Jabari Smith Jr.','小史密斯':'Jabari Smith Jr.','卡梅隆约翰逊':'Cameron Johnson','卡梅伦约翰逊':'Cameron Johnson',
 '克拉克斯顿':'Nic Claxton','托马斯':'Cam Thomas','卡姆托马斯':'Cam Thomas','鲍威尔':'Norman Powell','诺曼鲍威尔':'Norman Powell',
 '布朗尼詹姆斯':'Bronny James','小勒布朗詹姆斯':'Bronny James',
 '哈里森巴恩斯':'Harrison Barnes','哈里森巴恩':'Harrison Barnes','科比怀特':'Coby White','科比赫怀特':'Coby White',
 '朱霍勒迪':'Jrue Holiday','朱鲁霍勒迪':'Jrue Holiday','阿隆霍勒迪':'Aaron Holiday','贾斯廷霍勒迪':'Justin Holiday',
 '迈克尔波特':'Michael Porter Jr.','小迈克尔波特':'Michael Porter Jr.','凯文波特':'Kevin Porter Jr.','小凯文波特':'Kevin Porter Jr.',
 '克雷格波特':'Craig Porter Jr.','纳兹里德':'Naz Reid','保罗里德':'Paul Reed','塔里斯里德':'Tarris Reed Jr.',
 '格雷森阿伦':'Grayson Allen','格雷森艾伦':'Grayson Allen','贾勒特艾伦':'Jarrett Allen',
 '多诺万米切尔':'Donovan Mitchell','戴维恩米切尔':'Davion Mitchell','阿杰米切尔':'Ajay Mitchell',
 '德怀特鲍威尔':'Dwight Powell','德雷克鲍威尔':'Drake Powell',
 '谢登夏普':'Shaedon Sharpe','谢登莎普':'Shaedon Sharpe','戴龙夏普':'DayRon Sharpe','戴隆夏普':'DayRon Sharpe',
 '基肖恩乔治':'Kyshawn George','小德里克琼斯':'Derrick Jones Jr.','德里克琼斯':'Derrick Jones Jr.',
 '泰厄斯琼斯':'Tyus Jones','泰斯琼斯':'Tyus Jones','特雷琼斯':'Tre Jones','赫伯特琼斯':'Herb Jones',
 '格兰特威廉姆斯':'Grant Williams','杰拉米格兰特':'Jerami Grant',
}
TEAM_NAMES={v[0]:k for k,v in TEAMS.items()}
TEAM_NAMES.update({'费城':'PHI','七六人':'PHI','小牛':'DAL','开拓者队':'POR','雷霆队':'OKC','森林狼队':'MIN'})
TEAM_NAMES.update({'夏洛特黄蜂':'CHA','波士顿凯尔特人':'BOS','明尼苏达森林狼':'MIN','金州勇士':'GSW',
 '洛杉矶湖人':'LAL','洛杉矶快船':'LAC','纽约尼克斯':'NYK','布鲁克林篮网':'BKN','多伦多猛龙':'TOR',
 '费城76人':'PHI','克利夫兰骑士':'CLE','底特律活塞':'DET','印第安纳步行者':'IND','密尔沃基雄鹿':'MIL',
 '芝加哥公牛':'CHI','亚特兰大老鹰':'ATL','迈阿密热火':'MIA','奥兰多魔术':'ORL','华盛顿奇才':'WAS',
 '丹佛掘金':'DEN','俄克拉荷马雷霆':'OKC','波特兰开拓者':'POR','犹他爵士':'UTA','菲尼克斯太阳':'PHX',
 '萨克拉门托国王':'SAC','达拉斯独行侠':'DAL','休斯顿火箭':'HOU','孟菲斯灰熊':'MEM','新奥尔良鹈鹕':'NOP','圣安东尼奥马刺':'SAS'})
AMBIGUOUS={'鲍尔':['Ball'],'格林':['Green'],'穆雷':['Murray'],'默里':['Murray'],
           '威廉姆斯':['Williams'],'琼斯':['Jones'],'布里奇斯':['Bridges'],
           '汤普森':['Thompson'],'西蒙斯':['Simmons','Simons'],
           '怀特':['White'],'巴恩斯':['Barnes'],'波特':['Porter'],'小波特':['Porter'],
           '霍勒迪':['Holiday'],'阿伦':['Allen'],'艾伦':['Allen'],'里德':['Reid','Reed'],
           '米切尔':['Mitchell'],'鲍威尔':['Powell'],'夏普':['Sharpe'],'乔治':['George']}

# Remove only known query wording. A short surname must match the remaining
# name in full: an unrecognized Chinese given name must never be discarded.
QUERY_WORDS=(
 '20262027','202627','2026','2027','2627','nba','下个赛季','下赛季','这个赛季','本赛季','赛季',
 '我想知道','我想查','帮我查','查一下','查询','请问','请','帮我','告诉我','计算','估算','查',
 '实际到手','税后到手','净收入','税后','税前','实际','到手','年薪','薪水','工资','收入',
 '大概','大约','多少钱','是多少','多少','能拿到','可以拿到','能拿','拿到','的','球员','现在',
)

def clean(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',value).casefold() if c.isalnum())

def _query_name(query):
    key=clean(query)
    words=sorted({clean(x) for x in (*TEAM_NAMES,*QUERY_WORDS)},key=len,reverse=True)
    changed=True
    while changed and key:
        changed=False
        for word in words:
            if key.startswith(word):key=key[len(word):];changed=True;break
            if key.endswith(word):key=key[:-len(word)];changed=True;break
    return key

def _surname_matches(name,patterns):
    words=re.findall(r"[\w'-]+",name,flags=re.UNICODE)
    while words and clean(words[-1]) in ('jr','sr','ii','iii','iv','v'):words.pop()
    surname=words[-1] if words else ''
    pieces={clean(x) for x in re.split(r"[-']",surname)}|{clean(surname)}
    return bool(pieces&{clean(x) for x in patterns})

def _team_disambiguate(matches,query):
    team=mentioned_team(query)
    if not team or len(matches)<=1:return matches
    narrowed=[p for p in matches if p.get('team')==team or team in p.get('teams_in_active_roster_sections',[])]
    return narrowed if len(narrowed)==1 else matches

def resolve(players,query):
    key=clean(query)
    exact=[p for p in players if str(p['player_id'])==query or clean(p['player'])==key]
    if exact:return exact
    name_key=_query_name(query)
    for ambiguous,names in AMBIGUOUS.items():
        if name_key==clean(ambiguous):
            return _team_disambiguate([p for p in players if _surname_matches(p['player'],names)],query)
    for alias,name in ALIASES.items():
        if name_key==clean(alias):
            # A recognized full name missing from this snapshot is not a reason
            # to silently substitute a different player sharing its surname.
            return [p for p in players if clean(p['player'])==clean(name)]
    matches=[p for p in players if name_key and name_key in clean(p['player'])]
    return _team_disambiguate(matches,query)

def mentioned_team(query):
    for name,code in sorted(TEAM_NAMES.items(),key=lambda kv:len(kv[0]),reverse=True):
        if name in query:return code
    return None

def requires_clarification(players,query,matches):
    """A surname can stay ambiguous even when only one namesake has cached pay."""
    if _query_name(query) not in {clean(x) for x in AMBIGUOUS}:return False
    team=mentioned_team(query)
    return not (team and len(matches)==1 and
                (matches[0].get('team')==team or team in matches[0].get('teams_in_active_roster_sections',[])))
