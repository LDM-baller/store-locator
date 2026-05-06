"""Add Lululemon China-region stores (CN/HK/TW/MO) to data/lululemon.json.

Source: Lululemon's official China site lululemon.cn store-locator page,
provided by Lindsay 2026-05-06.

Approach:
- Stores are listed by city. Each store has a Chinese name + address + phone.
- Geocoding strategy: Nominatim-search "Lululemon <city_en>, <country>" gives the
  city centroid; we then slightly jitter each store within the city so they don't
  all stack on one pin. This is appropriate per Lindsay's earlier guidance ("city
  level fine for international, region level if no city, just note as estimated").
- All stores get coord_is_estimated=true and a citation pointing at lululemon.cn.

Year_opened: China debut Dec 2016 (Beijing + Shanghai + HK simultaneously per
Lulu corporate press release). Distributed via 10-K country-rank method using
existing CN/HK count progression in `data/_lulu_10k_store_counts.json`.
"""
import json, pathlib, re, time, datetime, urllib.request, urllib.parse, hashlib

DATA = pathlib.Path(r"G:\My Drive\Programs\store-map\data\lululemon.json")

# Structured list — each store is (country_iso, city_pinyin, name_zh, phone, status, store_type, address_zh).
# status: active | coming_soon | closed
# Closed stores will be dropped (per spec). Pop-ups (快闪) tagged store_type=popup.
STORES = [
    # 福州 (Fuzhou)
    ("CN", "Fuzhou", "北京三里屯-DUMMY", "", "active", "regular", ""),  # placeholder
]
# Will populate properly below.

STORES = [
  # (country, city_en, name_zh, phone, status, store_type, address_zh)

  # 福州 Fuzhou
  ("CN", "Fuzhou", "福州万象城",     "0591 28329936", "active", "regular", "福州市鼓楼区工业路东侧、福三路北侧、洪山园路地块的福州万象城L207+L208号商铺"),
  ("CN", "Fuzhou", "福州东百中心",   "059128082518",  "active", "regular", "福州市鼓楼区八一七北路132号东百中心第1F/2F层C2-102-2/C2-202-2"),

  # 北京 Beijing
  ("CN", "Beijing", "北京三里屯",          "010 64178818", "active", "flagship", "北京市朝阳区三里屯太古里北区NLG-53"),
  ("CN", "Beijing", "北京芳草地",          "010 56907198", "active", "regular", "北京市朝阳区东大桥路9号侨福芳草地中心L1-11单元"),
  ("CN", "Beijing", "北京apm",             "010 65121969", "active", "regular", "北京市东城区王府井大街138号新东安广场apm一层L116号"),
  ("CN", "Beijing", "北京颐堤港",          "010 84356061", "active", "regular", "北京市朝阳区酒仙桥路18号颐堤港1层L1-80号商铺"),
  ("CN", "Beijing", "北京来福士中心",      "010 84028813", "active", "regular", "北京市东城区东直门南大街1号北京来福士购物中心01层14/15/16号"),
  ("CN", "Beijing", "北京国贸商城",        "010 65305895", "active", "regular", "北京市朝阳区建国门外大街1号国贸商城地下一层的NB128A和NB128B号铺位"),
  ("CN", "Beijing", "北京朝阳大悦城",      "010 85833905", "active", "regular", "北京市朝阳区朝阳北路101号楼1层101内1F-21,22"),
  ("CN", "Beijing", "北京西单大悦城",      "010 58312889", "active", "regular", "北京市西城区西单北大街131号西单大悦城购物中心1F-37号商铺"),
  ("CN", "Beijing", "北京荟聚中心",        "010 60294028", "active", "regular", "北京市大兴区欣宁街15号北京荟聚中心1号楼1层4-01-94-SU铺位"),
  ("CN", "Beijing", "北京合生汇",          "010 67706966", "active", "regular", "北京市朝阳区西大望路甲22号院1号楼合生汇购物中心L1层L1-11,L1-12,L1-13A1号"),
  ("CN", "Beijing", "北京清河万象汇",      "010 62926308", "active", "regular", "北京市海淀区清河中街66号院1号楼华润清河万象汇L156A"),
  ("CN", "Beijing", "北京蓝色港湾",        "010 53383306", "active", "regular", "北京市朝阳区朝阳公园路6号院11号楼L-SA-36b、L-SA-36b1、L-SA-36b2号商铺"),
  ("CN", "Beijing", "北京长楹天街",        "010 85376527", "active", "regular", "北京市朝阳区常通路2号院1号楼龙湖·北京长楹天街B栋-1F-30,B栋-1F-31号房屋"),
  ("CN", "Beijing", "北京SKP",             "010 65919213", "active", "concession", "北京市朝阳区建国路87号华贸商城地下一层B1037-1号"),
  ("CN", "Beijing", "北京祥云小镇",        "010 80499175", "active", "outlet", "北京市顺义区安泰大街9号祥云小镇购物中心北区10-106号商铺"),
  ("CN", "Beijing", "北京DT51",            "01064976628",  "active", "regular", "朝阳区北苑路98号院1号楼DT51商场2层A2013号铺位"),
  ("CN", "Beijing", "北京颐堤港二店",      "01053329383",  "active", "regular", "北京市朝阳区酒仙桥路18号第1层第L178&L179号单元"),
  ("CN", "Beijing", "北京王府井中环中心",  "01053656727",  "active", "regular", "北京市东城区王府井大街269号院1号楼B1-101c&d单元"),
  ("CN", "Beijing", "北京京西大悦城",      "01056533133",  "active", "regular", "石景山区阜石路173号院1号楼京西大悦城1F-22"),
  ("CN", "Beijing", "北京亦庄天街",        "01050925170",  "active", "regular", "大兴区兴海路1号院1号楼北京亦庄天街A馆-1F-33b，A馆-1F-34"),
  ("CN", "Beijing", "北京八达岭奥莱",      "01053676703",  "active", "outlet", "昌平区南口路南口段1号院八达岭奥莱B区2号楼一层216号"),
  ("CN", "Beijing", "北京丽泽天街",        "010 86393578", "active", "regular", "丰台区丽泽路16号院1号楼龙湖·北京丽泽天街A馆-1F-14"),
  ("CN", "Beijing", "北京大兴国际机场",    "01053356931",  "active", "regular", "大兴区北京大兴国际机场航站楼出发层精品区西侧S-BL02-024,025,026"),
  ("CN", "Beijing", "北京首都国际机场T3",  "010 86392680", "active", "regular", "首都国际机场三号航站楼A3W8-1和A3W8-2"),
  ("CN", "Beijing", "北京世纪金源购物中心","010 86390625", "active", "regular", "海淀区远大路1号北京世纪金源购物中心1层1008号商铺"),
  ("CN", "Beijing", "北京大融城",          "010 67448975", "active", "regular", "北京市海淀区中关村大街15号北京大融城东区L1层42-46室"),

  # 台中 Taichung
  ("TW", "Taichung", "台中勤美誠品綠園道店", "886 4 2321 5253", "active", "regular", "台灣台中市西區公益路68號1樓L101-L102店"),

  # 泉州 Quanzhou
  ("CN", "Quanzhou", "泉州中骏世界城", "0595 22015227", "active", "regular", "丰泽区安吉南路869号的泉州中骏世界城M141/M142/M143单元"),

  # 呼和浩特 Hohhot
  ("CN", "Hohhot", "呼和浩特万象城", "0471 3415 358", "active", "regular", "内蒙古自治区呼和浩特市玉泉区大学西街70号呼和浩特万象城L108商铺"),

  # 长春 Changchun
  ("CN", "Changchun", "长春欧亚商都", "043189917191", "active", "regular", "朝阳区工农大路1128号长春欧亚商都A119号铺位"),
  ("CN", "Changchun", "长春万象城",   "043180690560", "active", "regular", "南关区人民大街3388号华润置地长春万象城L246号商铺"),

  # 南昌 Nanchang
  ("CN", "Nanchang", "南昌万象城",   "079182101201", "active", "regular", "红谷滩区学府大道388号南昌万象城L135号商铺"),
  ("CN", "Nanchang", "南昌武商MALL", "0791 86587639","active", "regular", "东湖区广场北路29号南昌武商MALL二层WSL2-25、26"),

  # 厦门 Xiamen
  ("CN", "Xiamen", "厦门万象城",        "0592 7032338",  "active", "regular", "厦门市思明区湖滨东路99号万象城L2层L235"),
  ("CN", "Xiamen", "厦门SM新生活广场",   "0592 3193 201", "active", "regular", "厦门市思明区嘉禾路399号、仙岳路1229号C130-C131号铺位"),

  # 重庆 Chongqing
  ("CN", "Chongqing", "重庆万象城",       "023 68630689", "active", "regular", "重庆市九龙坡区谢家湾正街55号万象城L2层L280"),
  ("CN", "Chongqing", "重庆北城天街",     "023 67001935", "active", "regular", "重庆市江北区北城天街6、8号龙湖北城天街A馆-1F-004"),
  ("CN", "Chongqing", "重庆金沙天街",     "023 65278037", "active", "regular", "重庆市沙坪坝区北站东路188号附3号龙湖·重庆金沙天街B馆-1F-45号房屋"),
  ("CN", "Chongqing", "重庆时代天街",     "023 86238638", "active", "regular", "重庆市渝中区时代天街A馆-L1-45,L1-46号"),
  ("CN", "Chongqing", "重庆光环购物公园", "023 63074350", "active", "regular", "渝北区湖彩路118号附1号重庆光环购物公园LG层A-LG-11,12号商铺"),
  ("CN", "Chongqing", "重庆江北机场T3",   "",             "coming_soon", "regular", "重庆江北国际机场T3航站楼安检内T3A-L320B、T3A-L321店铺"),

  # 南京 Nanjing
  ("CN", "Nanjing", "南京德基",        "025 51812073", "active", "regular", "南京市中山路18号德基广场二期三楼P301"),
  ("CN", "Nanjing", "南京万象天地",    "02557917535",  "active", "regular", "秦淮区中山南路666号南京万象天地L140&141&142号商铺"),
  ("CN", "Nanjing", "南京景枫中心",    "02552127396",  "active", "regular", "江宁区双龙大道1698号景枫中心商业购物中心1层F101铺位"),
  ("CN", "Nanjing", "南京IFC",         "02557950836",  "active", "regular", "建邺区江东中路345号国金中心商场四层L3-17室"),
  ("CN", "Nanjing", "南京JLC金陵中環", "025 52244728", "active", "regular", "秦淮区中山南路18号JLC金陵中環广场东区B1层B-B1-03,04,05号"),

  # 西安 Xi'an
  ("CN", "Xi'an", "西安大悦城",            "029 85720199", "active", "regular", "西安市雁塔区慈恩西路777号大悦城L1-33/32/74"),
  ("CN", "Xi'an", "西安老城根",            "029 81627096", "active", "regular", "西安市莲湖区星火路22号老城根Gpark 1F-12a、1F-12d铺位"),
  ("CN", "Xi'an", "西安赛格国际购物中心",  "029 89329751", "active", "regular", "西安市雁塔区小寨十字东北角赛格国际购物中心2层LL01号"),
  ("CN", "Xi'an", "西安大融城",            "02989299395",  "active", "regular", "经济技术开发区凤城七路51号购物中心主楼一楼L1-06、L1-05室"),
  ("CN", "Xi'an", "西安万象城",            "02989126883",  "active", "regular", "雁塔区长安南路与雁展路交汇处西安万象城L116+L117+L214"),
  ("CN", "Xi'an", "西安中大国际商业中心",  "029 89283616", "active", "regular", "陕西省西安市雁塔区高新路72号中大国际商业中心L127商铺"),
  ("CN", "Xi'an", "西安SKP",               "029 83698567", "active", "concession", "碑林区长安北路261号4层A4009"),

  # 深圳 Shenzhen
  ("CN", "Shenzhen", "深圳万象天地",       "0755 86542356","active", "flagship", "南山区深南大道9668号华润万象天地SL122、SL221号商铺"),
  ("CN", "Shenzhen", "深圳海岸城",         "0755 26912807","active", "regular", "南山区文心五路33号海岸城广场2层258-259号商铺"),
  ("CN", "Shenzhen", "深圳星河COCO Park",  "0755 83201171","active", "regular", "福田区福华三路268号星河COCOPARK购物广场L1S-090/089/091/092"),
  ("CN", "Shenzhen", "深圳壹方城",         "0755 27087815","active", "regular", "宝安区新湖路99号壹方城一层L1-092/093/093A"),
  ("CN", "Shenzhen", "深圳京基百纳空间",   "0755 82246742","active", "regular", "罗湖区蔡屋围京基金融中心裙楼01层101B、101C号商铺"),
  ("CN", "Shenzhen", "深圳龙华壹方城",     "0755 21034169","active", "regular", "龙华区壹方天地C区L1层L1-040/041/042/043号"),
  ("CN", "Shenzhen", "深圳万象前海",       "0755 82221292","active", "regular", "前海深港合作区桂湾四路169号万象前海购物中心L149号商铺"),
  ("CN", "Shenzhen", "深圳宝安机场卫星厅", "0755 36568827","active", "regular", "宝安区宝安大道宝安国际机场卫星厅3D004号"),
  ("CN", "Shenzhen", "深圳龙岗万科",       "0755 84510537","active", "regular", "龙岗区龙翔大道7188号万科广场L1层40-41号铺位"),
  ("CN", "Shenzhen", "深圳茂业广场",       "0755 83149265","active", "regular", "福田区华强北路2009号茂业百货深圳华强1层F01013X号商铺"),
  ("CN", "Shenzhen", "深圳布吉万象汇",     "0755 28459095","active", "regular", "龙岗区布吉街道翔鸽路2号华润万象汇购物中心L137铺位"),
  ("CN", "Shenzhen", "深圳深业上城",       "075523600563", "active", "regular", "福田区皇岗路5001号深业上城L3层T3025B&T3026&T3052号商铺"),
  ("CN", "Shenzhen", "深圳万象城",         "075525128112", "active", "flagship", "罗湖区宝安南路1881号深圳万象城L368"),
  ("CN", "Shenzhen", "深圳宝安机场T3",     "0755 23459782","active", "regular", "宝安区宝安国际机场T3航站楼3S-09-04"),

  # 广州 Guangzhou
  ("CN", "Guangzhou", "广州太古汇",         "020 89811591","active", "flagship", "天河区383号太古汇商场裙楼地铁上层MU48号商铺"),
  ("CN", "Guangzhou", "广州天汇广场",       "020 88525186","active", "regular", "天河区珠江新城兴民路222号L123"),
  ("CN", "Guangzhou", "广州天环广场",       "020 83622371","active", "regular", "天河区天河路218号L119c及L119d商铺"),
  ("CN", "Guangzhou", "广州白云机场T2",     "020 32782373","active", "regular", "广州白云机场T2西连廊二层T22R27A、T22R26B、T22R26A"),
  ("CN", "Guangzhou", "广州聚龙湾太古里",   "020 81777634","active", "regular", "荔湾区芳村大道东146-166号广州聚龙湾太古里W区03栋W03-L101A"),

  # 成都 Chengdu
  ("CN", "Chengdu", "成都万象城",        "028 83254221","active", "regular", "成华区华润万象城1楼南庭163店铺"),
  ("CN", "Chengdu", "成都太古里",        "028 86768266","active", "flagship", "锦江区中纱帽街8号1313、2307a+2305及三层铺位"),
  ("CN", "Chengdu", "成都仁和新城",      "028 63292886","active", "regular", "武侯区府城大道西段505号仁和新城1楼183、189、190号铺位"),
  ("CN", "Chengdu", "成都大悦城",        "028 62250052","active", "regular", "武侯区大悦路518号成都大悦城1F-036A、036B、036C号商铺"),
  ("CN", "Chengdu", "成都SKP",           "028 60831320","active", "concession", "武侯区天府大道北段2001号二层D2179-1号"),
  ("CN", "Chengdu", "成都世豪广场",      "02865170660", "active", "regular", "武侯区剑南大道中段998号成都世豪购物中心高新店1层C124b、C107号铺位"),
  ("CN", "Chengdu", "成都佛罗伦萨小镇",  "02887980291", "active", "outlet", "郫都区友爱镇银杏路888号一楼O1&O2单元"),
  ("CN", "Chengdu", "成都双流国际机场",  "028 85207141","active", "regular", "成都双流国际机场航站楼出发层EF-R-1D场地"),
  ("CN", "Chengdu", "成都西宸天街",      "028 83513808","active", "regular", "金牛区花照壁西顺街399号一层A馆-1F-47、48a、60、61"),

  # 太原 Taiyuan
  ("CN", "Taiyuan", "太原茂业天地", "0351 2531337","active", "regular", "小店区亲贤北街79号太原茂业购物中心F01-15号铺位"),
  ("CN", "Taiyuan", "太原万象城",   "03515625860", "active", "regular", "万柏林区长风商务区长兴路5号太原万象城1层L134a号铺位"),

  # 苏州 Suzhou
  ("CN", "Suzhou", "苏州中心",           "0512 61790585","active", "regular", "吴中区苏州中心广场2幢01层B 01-29/30/31号"),
  ("CN", "Suzhou", "苏州大悦春风里",     "0512 65163681","active", "regular", "相城区元和街道御窑路1999号大悦春风里L1-16号商铺"),
  ("CN", "Suzhou", "苏州仁恒仓街商业广场","051267707011","active", "regular", "姑苏区仓街1号3-C号楼第G层151号及第UG层221号商铺"),
  ("CN", "Suzhou", "比斯特苏州购物村",   "051265036620","active", "outlet", "苏州工业园区唯亭阳澄环路969号比斯特苏州购物村30-103和30-104单元"),
  ("CN", "Suzhou", "苏州狮山天街",       "051288869856","active", "regular", "虎丘区塔园路181号苏州狮山天街A-1F-33、34"),

  # 佛山 Foshan
  ("CN", "Foshan", "佛山岭南站",         "075763999261","active", "regular", "禅城区祖庙路29号第一层006号铺位"),
  ("CN", "Foshan", "佛山佛罗伦萨小镇",   "075781251120","active", "outlet", "南海区桂城街道疏港路28号佛罗伦萨小镇广佛奥特莱斯购物中心一楼38-01/02/03/04单元"),

  # 沈阳 Shenyang
  ("CN", "Shenyang", "沈阳万象城",     "024 31518998","active", "regular", "和平区青年大街288号沈阳华润中心万象城2层L260号商铺"),
  ("CN", "Shenyang", "沈阳皇城恒隆",   "024 23930515","active", "regular", "沈河区中街路128号皇城恒隆广场121-122号店铺"),
  ("CN", "Shenyang", "沈阳铁西万象汇", "02423873992", "active", "regular", "铁西区建设东路158号华润万象汇L138号铺位"),

  # 贵阳 Guiyang
  ("CN", "Guiyang", "贵阳亨特城市广场", "",            "closed", "regular", "南明区机场路18号亨特国际地下室幢负2层1B 157、158号商铺"),
  ("CN", "Guiyang", "贵阳万象汇",       "085182210090","active", "regular", "观山湖区兴筑西路88号贵阳万象汇L124"),
  ("CN", "Guiyang", "贵阳万象城",       "0851 88581880","active", "regular", "南明区遵义路328号贵阳万象城L113A"),

  # 杭州 Hangzhou
  ("CN", "Hangzhou", "杭州大厦",          "0571 87838903","active", "concession", "武林广场1号杭州大厦购物城B座四层401单元"),
  ("CN", "Hangzhou", "杭州湖滨银泰in77",  "0571 86011957","active", "flagship", "杭州湖滨银泰in77 A区D3-L1&-L2室铺位"),
  ("CN", "Hangzhou", "杭州万象城",        "0571 89702059","active", "regular", "上城区富春路701号杭州万象城B1层B178号商铺"),
  ("CN", "Hangzhou", "杭州城西银泰",      "0571 87031890","active", "regular", "拱墅区丰潭路380号城西银泰城1F008A&008B号铺位"),
  ("CN", "Hangzhou", "杭州滨江天街",      "0571 86033611","active", "regular", "滨江区江汉路1515号龙湖·杭州滨江天街01-1F-18b、19号"),
  ("CN", "Hangzhou", "杭州萧山万象汇",    "057186817970","active", "regular", "萧山区北干街道金城路927号L168"),
  ("CN", "Hangzhou", "杭州西溪印象城",    "057126250831","active", "regular", "余杭区五常大道1号01-88西溪印象城MA栋L1层P1-01-54-57号"),
  ("CN", "Hangzhou", "杭州恒隆广场",      "",            "coming_soon", "regular", "拱墅区体育场路321号杭州恒隆广场LG1-49&LG2-37号铺位"),

  # 金华 Jinhua
  ("CN", "Jinhua", "金华世贸广场", "057982677982","active", "regular", "婺城区三江街道李渔路888号金华世贸城市广场E区一层1F-E016号"),

  # 香港 Hong Kong
  ("HK", "Hong Kong", "希慎廣場",       "852 26236151","active", "regular", "香港銅鑼灣軒尼詩道500號希慎廣場104-105號"),
  ("HK", "Hong Kong", "新城市廣場",     "852 22346433","active", "regular", "香港沙田正街18號新城市廣場1期L4 469號"),
  ("HK", "Hong Kong", "國際金融中心商場","852 29977170","active", "regular", "香港中環金融街8號國際金融中心商場1098B號"),
  ("HK", "Hong Kong", "太古廣場",       "852 28105168","active", "regular", "香港金鐘金鐘道88號太古廣場119號"),
  ("HK", "Hong Kong", "海港城港威商場", "852 23240811","active", "regular", "香港尖沙咀海港城港威商場3樓3223A號"),
  ("HK", "Hong Kong", "又一城",         "852 24726568","active", "regular", "九龍塘達之路80號又一城LG1-25號"),
  ("HK", "Hong Kong", "皇后大道中",     "852 24630053","active", "flagship", "香港中環皇后大道中80號H Queen 地下及M樓1號及1B號"),
  ("HK", "Hong Kong", "圓方",           "852 27025338","active", "regular", "九龍尖沙咀柯士甸道西1號圓方1樓1084-1085號"),

  # 常州 Changzhou
  ("CN", "Changzhou", "常州万象城", "051988099660","active", "regular", "天宁区茶山街道离宫路329号常州万象城L1FL118、L119号商铺"),

  # 台北 Taipei
  ("TW", "Taipei", "台北忠孝大安",    "886 2 27751486","active", "regular", "台北市大安區敦化南路一段187巷41號"),
  ("TW", "Taipei", "台北新光三越A8",  "886 2 27228681","active", "regular", "台北市110信義區松高路12號1樓"),
  ("TW", "Taipei", "台北101",         "886 2 81018283","active", "flagship", "台北市信義區市府路45號B1-61A"),
  ("TW", "Taipei", "台北微風廣場",    "886 2 8772 6805","active", "regular", "台北市松山區復興南路一段39號G/F"),

  # 上海西岸中環 (Shanghai Xiyan Zhonghuan, separate listing)
  ("CN", "Shanghai", "上海西岸中環", "02160125330","coming_soon", "regular", "上海市徐汇区大木桥路798-1号1幢L1层B-L1-41/42/43/44号商铺"),

  # 澳门 Macau
  ("MO", "Macau", "威尼斯人購物中心",       "853 28438121","active", "regular", "澳門氹仔聖母灣大馬路威尼斯人購物中心3樓大運河街2421號"),
  ("MO", "Macau", "澳門倫敦人購物中心",     "853 28420665","active", "regular", "澳門路路氹連貫公路澳門金沙城中心2樓2031及2242號"),

  # 三亚 Sanya
  ("CN", "Sanya", "三亚海旅免税店",     "0898 38218997","active", "regular", "吉阳区迎宾303号L2-C-01&02铺位"),
  ("CN", "Sanya", "三亚国际免税城",     "089896656",    "active", "regular", "海棠区海棠北路118号三亚国际免税城A座三层F326"),

  # 武汉 Wuhan
  ("CN", "Wuhan", "武汉武商MALL",   "027 85588018","active", "concession", "江汉区解放大道690号武商MALL二层C2-3A柜位"),
  ("CN", "Wuhan", "武汉恒隆广场",   "027 85883268","active", "regular", "硚口区京汉大道668号恒隆广场L224铺位"),
  ("CN", "Wuhan", "武汉武商梦时代", "027 59307055","active", "regular", "武昌区武珞路598号武商梦时代一楼A-110、A-111店铺"),
  ("CN", "Wuhan", "武汉SKP",        "02759611961", "active", "concession", "武昌区水果湖街汉街武汉中央文化旅游区J3地块5栋1-2层A1002+A2002号"),
  ("CN", "Wuhan", "武汉天地",       "02782280128", "active", "regular", "江岸区中山大道1618号武汉天地A4地块1期1号楼1-1-1A1、1-2-1A1单元"),

  # 温州 Wenzhou
  ("CN", "Wenzhou", "温州印象城MEGA","0577 28980085","active", "regular", "鹿城区南汇街道府东路333号温印商业中心D29-L1-02+03号商铺"),
  ("CN", "Wenzhou", "温州万象城",     "0577 86729115","active", "regular", "瓯海区南白象街道瓯越大道1999号温州万象城L141-L142"),

  # 昆明 Kunming
  ("CN", "Kunming", "昆明恒隆",       "0871 63389100","active", "regular", "盘龙区东风东路21号昆明恒隆广场L210C号商铺"),
  ("CN", "Kunming", "昆明顺城购物中心","0871 63648420","active", "regular", "五华区东风西路7号顺城购物中心C1-10B & T-104商铺"),
  ("CN", "Kunming", "昆明长水机场T1", "0871 67086045","active", "regular", "昆明长水机场T1航站楼安检内中指廊F3CA21"),
  ("CN", "Kunming", "昆明同德广场",   "0871 68271165","active", "regular", "盘龙区北京路928号同德广场商场A5-F1楼07、08号商铺"),

  # 海口 Haikou
  ("CN", "Haikou", "海口万象城",     "0898 36607760","active", "regular", "龙华区金贸街道金贸东路4号海口万象城L213铺位"),
  ("CN", "Haikou", "海口国际免税城", "089896656",    "active", "regular", "秀英区滨海大道170号海口国际免税城三层L3-15号铺位"),

  # 天津 Tianjin
  ("CN", "Tianjin", "天津万象城",       "022 83887638","active", "regular", "河西区乐园道9号天津万象城L2-003号商铺"),
  ("CN", "Tianjin", "天津佛罗伦萨小镇", "02282128710", "active", "outlet", "武清区前进道北侧天津佛罗伦萨小镇院一楼167&168单元"),
  ("CN", "Tianjin", "天津南开大悦城",   "02258578695", "active", "regular", "南开区南门外大街2号天津大悦城购物中心1F-18/19、2F-19a/19b"),

  # 哈尔滨 Harbin
  ("CN", "Harbin", "哈尔滨远大购物中心", "0451 58762160","active", "regular", "南岗区荣市街18号远大购物中心一拖二层006号铺位"),
  ("CN", "Harbin", "哈尔滨西城红场",     "+86 0451 51021766","active", "regular", "南岗区哈西大街299号西城红场一层F1B032-2商铺"),

  # 青岛 Qingdao
  ("CN", "Qingdao", "青岛万象城",     "0532 85813298","active", "regular", "市南区青岛万象城G112/113号商铺"),
  ("CN", "Qingdao", "青岛海信广场",   "0532 55687618","active", "concession", "市南区澳门路117号青岛海信广场0204号柜位"),
  ("CN", "Qingdao", "青岛崂山万象汇", "053255795790","active", "regular", "崂山区深圳路101号青岛崂山万象汇L138、L138a铺位"),

  # 珠海 Zhuhai
  ("CN", "Zhuhai", "珠海华发商都", "07566841135","active", "regular", "香洲区珠海大道8号华发商都1层A1010a、A1012a号铺位"),

  # 无锡 Wuxi
  ("CN", "Wuxi", "无锡恒隆广场", "0510 85205669","active", "flagship", "梁溪区人民中路139-101号恒隆广场2楼218/219单元"),
  ("CN", "Wuxi", "无锡海岸城",   "0510 85182589","active", "regular", "滨湖区经济开发区海岸城A座39-101-1商铺"),

  # 东莞 Dongguan
  ("CN", "Dongguan", "东莞民盈国贸城", "076988650906","active", "regular", "东城街道鸿福东路1号民盈国贸城L1002-L1003号铺位"),

  # 郑州 Zhengzhou
  ("CN", "Zhengzhou", "郑州丹尼斯大卫城", "0371 89819591","active", "regular", "金水区北二七路188号丹尼斯大卫城2F-B010"),
  ("CN", "Zhengzhou", "郑州正弘城",       "0371-63316536","active", "regular", "金水区花园路126号正弘城2层L206A号铺位"),
  ("CN", "Zhengzhou", "郑州郑东万象城",   "0371 55238335","active", "regular", "金水区金水东路67号郑州郑东万象城L108商铺"),
  ("CN", "Zhengzhou", "郑州银泰inPARK",   "0371 55238608","active", "regular", "北龙湖金融岛4区1层L1001室"),

  # 长沙 Changsha
  ("CN", "Changsha", "长沙王府井",  "073182567308","active", "concession", "天心区黄兴中路27号王府井百货一/二层东南角铺位"),
  ("CN", "Changsha", "长沙万象城",  "073188609078","active", "regular", "岳麓区桐梓坡路与桐北巷交叉口往南200米长沙万象城L109号商铺"),

  # 大连 Dalian
  ("CN", "Dalian", "大连柏威年中心", "0411 84176507","active", "regular", "中山区中山路129-3号L1001铺位"),
  ("CN", "Dalian", "大连恒隆广场",   "0411 83784205","active", "flagship", "西岗区五四路66号大连恒隆广场B13号铺位"),

  # 石家庄 Shijiazhuang
  ("CN", "Shijiazhuang", "石家庄万象城",   "031166099616","active", "regular", "桥西区中山西路108号石家庄万象城L143、L144号商铺"),
  ("CN", "Shijiazhuang", "石家庄北国商城", "0311 85311703","active", "concession", "桥西区中山东路188号北国商城L1, M-11-12铺位"),

  # 南宁 Nanning
  ("CN", "Nanning", "南宁万象城", "0771 2553990","active", "regular", "青秀区民族大道136号南宁华润中心万象城L2层226号商铺"),

  # 南通 Nantong
  ("CN", "Nantong", "南通万象城", "0513-85560723","active", "regular", "崇川区北大街111号南通万象城L168商铺"),

  # 宁波 Ningbo
  ("CN", "Ningbo", "宁波和义大道",     "0574 87916781","active", "regular", "海曙区和义路66号和义大道购物中心二层2009A号商铺"),
  ("CN", "Ningbo", "宁波万象城",       "057427996321","active", "regular", "江北区清河路265号宁波万象城购物中心1F-L121A号商铺"),
  ("CN", "Ningbo", "宁波杉井奥特莱斯", "0574 87627313","active", "outlet", "海曙区春华路1399号杉井奥特莱斯15500+15600+15610+15700+15800铺位"),

  # 惠州 Huizhou
  ("CN", "Huizhou", "惠州华贸天地", "07522866650","active", "regular", "惠城区江北文昌一路9号一层1114号、1115号"),

  # 济南 Jinan
  ("CN", "Jinan", "济南恒隆广场", "0531 86025652","active", "flagship", "历下区泉城路188号济南恒隆广场119/136/136A号铺位"),
  ("CN", "Jinan", "济南万象城",   "053155551670","active", "regular", "历下区经十路11111号济南万象城L217、L219号商铺"),

  # 徐州 Xuzhou
  ("CN", "Xuzhou", "徐州金鹰购物中心", "0516 82500079","active", "concession", "鼓楼区中山北路2号金鹰购物中心1层F1016号"),

  # 合肥 Hefei
  ("CN", "Hefei", "合肥银泰",      "0551 65208889","active", "concession", "庐阳区长江中路98号银泰中心F2-2003铺位"),
  ("CN", "Hefei", "合肥银泰in77",  "0551-66038068","active", "regular", "蜀山区祁门路333号合肥银泰in77 1F层L1050-L1051室铺位"),

  # 绍兴 Shaoxing
  ("CN", "Shaoxing", "绍兴银泰百货", "0575 88688996","active", "concession", "越城区解放南路777号绍兴银泰百货F1层1005-1号"),

  # 兰州 Lanzhou
  ("CN", "Lanzhou", "兰州中心", "09312302069","active", "regular", "七里河区西津西路16号兰州中心1F层1-L10店铺"),

  # 嘉兴 Jiaxing
  ("CN", "Jiaxing", "嘉兴八佰伴", "","coming_soon", "regular", "南湖区中山东路1360号嘉兴八佰伴一层6019L1022号"),

  # 上海 Shanghai (main listing)
  ("CN", "Shanghai", "上海静安嘉里",      "021 61810950","active", "flagship", "静安区南京西路1515号东区L1-L2层E1-01、E2-01单元"),
  ("CN", "Shanghai", "上海浦东IFC",       "021 61059267","active", "regular", "浦东新区世纪大道8号国金中心地下一层LG1-32室"),
  ("CN", "Shanghai", "上海兴业太古汇",    "021 61409600","active", "regular", "静安区南京西路789号兴业太古汇2楼L251"),
  ("CN", "Shanghai", "上海新天地",        "021 63768803","active", "flagship", "黄浦区兴业路123弄1号01a-02单元"),
  ("CN", "Shanghai", "上海港汇",          "021 33682373","active", "regular", "徐汇区虹桥路1号港汇广场166A单元"),
  ("CN", "Shanghai", "上海比斯特购物村",  "021 68772719","active", "outlet", "浦东新区申迪东路88号I6单元"),
  ("CN", "Shanghai", "上海浦东嘉里城",    "021 58333689","active", "regular", "浦东新区花木路1378号浦东嘉里城商场一层L115号及L116号单元"),
  ("CN", "Shanghai", "上海七宝领展广场",  "021 61921338","active", "regular", "闵行区漕宝路3366号七宝领展广场L117A"),
  ("CN", "Shanghai", "上海合生汇",        "021 61421369","active", "regular", "杨浦区翔殷路1099号上海合生汇国际广场L1-09A&L1-09B号商铺"),
  ("CN", "Shanghai", "上海世纪汇",        "021 50777901","active", "regular", "浦东新区世纪大道1192号世纪汇广场L1层013+014+015+KL1-01号铺位"),
  ("CN", "Shanghai", "上海虹桥机场店",    "021 22382629","active", "regular", "长宁区虹桥路2550号虹桥国际机场T2 D40-18A和D40-18B铺位"),
  ("CN", "Shanghai", "上海久光中心",      "021 66288125","active", "regular", "静安区共和新路2188号利福国际中心M101-3+M101-4号铺位"),
  ("CN", "Shanghai", "上海环球港",        "021 60193584","active", "regular", "普陀区中山北路3300号环球港一层L1008号铺"),
  ("CN", "Shanghai", "上海瑞虹天地太阳宫","021 65155716","active", "regular", "虹口区瑞虹路181号1层117号商铺"),
  ("CN", "Shanghai", "上海iapm",          "021 61252050","active", "regular", "徐汇区淮海中路999号上海环贸广场三层L3 305室"),
  ("CN", "Shanghai", "上海东平路",        "02164080288", "active", "flagship", "徐汇区东平路9号全幢104室"),
  ("CN", "Shanghai", "上海天空万科广场",  "02159860918", "active", "regular", "青浦区崧泽大道2229弄66号上海天空万科广场L1-18/19号铺位"),
  ("CN", "Shanghai", "上海长宁来福士",    "02152555583", "active", "regular", "长宁区长宁路1181号H1 01层01/02号及H1 02层01号"),
  ("CN", "Shanghai", "上海青浦百联奥特莱斯广场","021 59202763","active", "outlet", "青浦区沪青平公路2888号百联奥特莱斯广场B165号"),
  ("CN", "Shanghai", "上海南翔印象城Mega","021 60139690","active", "regular", "嘉定区陈翔公路2299号上海南翔印象城MEGA第01-58+59+60号"),
  ("CN", "Shanghai", "上海西郊百联购物中心","021 52680087","active", "regular", "长宁区仙霞西路88号F01层G05-01F01-01-0045-0049室"),
  ("CN", "Shanghai", "上海西岸梦中心",    "021 60711711","active", "regular", "徐汇区龙腾大道2260号西岸梦中心第4栋一层120商铺"),
  ("CN", "Shanghai", "上海松江印象城",    "021 60797707","active", "regular", "松江区广富林路1788弄1号上海松江印象城L131-133号"),
  ("CN", "Shanghai", "上海万象城",        "021 60123895","active", "flagship", "闵行区吴中路1599号上海万象城L105商铺"),
  ("CN", "Shanghai", "上海置汇旭辉广场购物中心","021 61187153","active", "regular", "张杨路2389弄1-2号置汇旭辉广场购物中心LCM 1F-44、45号商铺"),
  ("CN", "Shanghai", "上海真如环宇城MAX", "021 60963571","active", "regular", "普陀区铜川路699弄1号上海真如环宇城MAX L1层L1041+1059+1060"),
  ("CN", "Shanghai", "上海浦东新嘉中心",  "",            "active", "regular", "浦东新区张杨北路1199号新嘉中心LG-15商铺"),
]

# City centroids (lat, lng) — used as base coords; each store gets a small jitter
# within the city so they don't all stack on one pin.
CITY_CENTROIDS = {
    ("CN","Beijing"):     (39.9042, 116.4074),
    ("CN","Shanghai"):    (31.2304, 121.4737),
    ("CN","Shenzhen"):    (22.5429, 114.0596),
    ("CN","Guangzhou"):   (23.1291, 113.2644),
    ("CN","Chengdu"):     (30.5728, 104.0668),
    ("CN","Chongqing"):   (29.5630, 106.5516),
    ("CN","Hangzhou"):    (30.2741, 120.1551),
    ("CN","Nanjing"):     (32.0603, 118.7969),
    ("CN","Xi'an"):       (34.3416, 108.9398),
    ("CN","Wuhan"):       (30.5928, 114.3055),
    ("CN","Suzhou"):      (31.2989, 120.5853),
    ("CN","Tianjin"):     (39.3434, 117.3616),
    ("CN","Qingdao"):     (36.0671, 120.3826),
    ("CN","Shenyang"):    (41.8057, 123.4315),
    ("CN","Dalian"):      (38.9140, 121.6147),
    ("CN","Xiamen"):      (24.4798, 118.0894),
    ("CN","Fuzhou"):      (26.0745, 119.2965),
    ("CN","Quanzhou"):    (24.8741, 118.6755),
    ("CN","Hohhot"):      (40.8424, 111.7497),
    ("CN","Changchun"):   (43.8868, 125.3245),
    ("CN","Nanchang"):    (28.6820, 115.8579),
    ("CN","Taiyuan"):     (37.8706, 112.5489),
    ("CN","Foshan"):      (23.0218, 113.1216),
    ("CN","Guiyang"):     (26.6470, 106.6302),
    ("CN","Jinhua"):      (29.0792, 119.6473),
    ("CN","Changzhou"):   (31.7728, 119.9540),
    ("CN","Sanya"):       (18.2528, 109.5119),
    ("CN","Wenzhou"):     (27.9938, 120.6993),
    ("CN","Kunming"):     (24.8801, 102.8329),
    ("CN","Haikou"):      (20.0444, 110.1989),
    ("CN","Harbin"):      (45.8038, 126.5340),
    ("CN","Zhuhai"):      (22.2710, 113.5767),
    ("CN","Wuxi"):        (31.4912, 120.3119),
    ("CN","Dongguan"):    (23.0207, 113.7518),
    ("CN","Zhengzhou"):   (34.7466, 113.6253),
    ("CN","Changsha"):    (28.2282, 112.9388),
    ("CN","Shijiazhuang"):(38.0428, 114.5149),
    ("CN","Nanning"):     (22.8170, 108.3669),
    ("CN","Nantong"):     (32.0299, 120.8581),
    ("CN","Ningbo"):      (29.8683, 121.5440),
    ("CN","Huizhou"):     (23.1115, 114.4159),
    ("CN","Jinan"):       (36.6512, 117.1201),
    ("CN","Xuzhou"):      (34.2042, 117.2857),
    ("CN","Hefei"):       (31.8206, 117.2272),
    ("CN","Shaoxing"):    (29.9939, 120.5810),
    ("CN","Lanzhou"):     (36.0611, 103.8343),
    ("CN","Jiaxing"):     (30.7522, 120.7505),
    ("HK","Hong Kong"):   (22.3193, 114.1694),
    ("MO","Macau"):       (22.1987, 113.5439),
    ("TW","Taipei"):      (25.0330, 121.5654),
    ("TW","Taichung"):    (24.1477, 120.6736),
}

COUNTRY_NAMES = {"CN":"China", "HK":"Hong Kong", "TW":"Taiwan", "MO":"Macau"}


def jittered(lat, lng, idx, total):
    """Distribute stores in a small grid around the city centroid (~0.5-1km spacing)."""
    import math
    if total == 1: return lat, lng
    # Spiral pattern
    angle = (idx * 137.508) * math.pi / 180  # golden angle
    radius = 0.005 * math.sqrt(idx + 1)  # scale ~500m * sqrt(N)
    return lat + radius * math.cos(angle), lng + radius * math.sin(angle)


def slugify(s):
    s = re.sub(r'[^\w\s-]', '', s.lower())
    s = re.sub(r'[\s-]+', '-', s).strip('-')
    return s or "x"


def main():
    print(f"Loading {DATA.name} ...")
    file = json.loads(DATA.read_text(encoding="utf-8"))
    existing_count = len(file["stores"])
    print(f"  existing stores: {existing_count}")

    # Drop closed stores per spec
    active_stores = [s for s in STORES if s[4] != "closed"]
    print(f"\nChina-region stores from lululemon.cn: {len(STORES)} listed; {len(STORES)-len(active_stores)} closed (dropped)")

    # Group by city to compute jitter index
    from collections import defaultdict
    by_city = defaultdict(list)
    for s in active_stores:
        by_city[(s[0], s[1])].append(s)

    new_records = []
    scraped_at = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    for (cc, city), city_stores in by_city.items():
        centroid = CITY_CENTROIDS.get((cc, city))
        if not centroid:
            print(f"  WARN: no centroid for {cc}/{city}")
            continue
        for idx, (cc, city, name, phone, status, store_type, address) in enumerate(city_stores):
            lat, lng = jittered(centroid[0], centroid[1], idx, len(city_stores))
            sid = f"lululemon-{cc.lower()}-{slugify(name)}"[:80]
            new_records.append({
                "id": sid,
                "retailer": "Lululemon",
                "name": name,
                "address": address,
                "city": city,
                "state": None,
                "country": cc,
                "postal_code": None,
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "coord_is_estimated": True,
                "store_type": store_type,
                "status": status,
                "phone": phone or None,
                "hours": None,
                "url": None,
                "year_opened": None,  # will be set by estimator
                "year_opened_validation": "pending",
                "scraped_at": scraped_at,
                "raw": {
                    "_coord_source": "city-centroid-jittered",
                    "_city_centroid": centroid,
                    "_data_source": "Lululemon official China store-locator (lululemon.cn), provided 2026-05-06",
                    "address_zh": address,
                    "name_zh": name,
                    "country_name": COUNTRY_NAMES.get(cc, cc),
                },
            })

    print(f"\nNew records to add: {len(new_records)}")
    by_country = defaultdict(int)
    for r in new_records: by_country[r["country"]] += 1
    print(f"  by country: {dict(by_country)}")

    # Append to lululemon.json
    file["stores"].extend(new_records)
    file["store_count"] = len(file["stores"])
    file["scope"] = "global (NA via Next.js SSR + intl from regional Demandware sites + China region from lululemon.cn)"
    DATA.write_text(json.dumps(file, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {file['store_count']} stores to {DATA}")


if __name__ == "__main__":
    main()
