#!/usr/bin/env python3
"""Render the book's authored numerical diagrams. Standard library only."""
from html import escape
from pathlib import Path

OUT = Path(__file__).parent / 'assets' / 'diagrams'
INK, MUTED, LINE, BLUE, RUST, PALE = '#202b32', '#56616b', '#bfc8cc', '#245d79', '#a14929', '#e7eef0'


def text(x, y, value, size=18, fill=INK, anchor='start'):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" text-anchor="{anchor}">{escape(str(value))}</text>'


def rect(x, y, w, h, fill=PALE, stroke=LINE):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}"/>'


def line(x1, y1, x2, y2, color=LINE, dash=False):
    d = ' stroke-dasharray="6 5"' if dash else ''
    return f'<path d="M{x1} {y1} L{x2} {y2}" stroke="{color}" stroke-width="2" fill="none"{d}/>'


def arrow(x1, y1, x2, y2, color=BLUE):
    import math
    a = math.atan2(y2-y1, x2-x1)
    points = [(x2, y2), (x2-10*math.cos(a-.4), y2-10*math.sin(a-.4)),
              (x2-10*math.cos(a+.4), y2-10*math.sin(a+.4))]
    return line(x1, y1, x2, y2, color) + '<polygon points="' + ' '.join(f'{x:.1f},{y:.1f}' for x,y in points) + f'" fill="{color}"/>'


def box(x, y, w, h, title, detail='', fill=PALE):
    return (rect(x,y,w,h,fill) + text(x+14,y+29,title,19)
            + (text(x+14,y+55,detail,15,MUTED) if detail else ''))


def save(name, title, body, height=440):
    OUT.mkdir(parents=True, exist_ok=True)
    # No reusable IDs: every SVG is also safe to inline in the combined volume.
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 {height}" role="img" aria-label="{escape(title, quote=True)}"><title>{escape(title)}</title><rect width="960" height="{height}" fill="#faf9f4"/><g font-family="Noto Sans CJK SC,system-ui,sans-serif">{text(30,40,title,25)}{body}</g></svg>'''
    (OUT / f'{name}.svg').write_text(svg + '\n')


def render():
    b = ''
    for y, label in [(100,'接入'),(210,'引擎'),(330,'准备')]:
        b += text(30,y+30,label,18,MUTED) + line(115,y+65,925,y+65)
    b += box(140,85,210,68,'身份与限额','请求 ID / 模型权限') + arrow(350,118,405,118)
    b += box(410,85,210,68,'模板与分词','形成实际 token 序列')
    b += arrow(515,153,515,205)
    b += box(140,205,210,68,'等待资源','预算、序列数、KV 块')
    b += arrow(515,190,245,205) + arrow(350,238,405,238)
    b += box(410,205,210,68,'GPU 组执行','多 rank 协作') + arrow(620,238,675,238)
    b += box(680,205,240,68,'解码与回传','设备时间 ≠ 收到时间')
    b += box(140,325,240,68,'节点 / 设备 / 模型','控制面先准备容量')
    b += line(380,350,510,280,BLUE,True) + text(550,366,'虚线：准备依赖，不是每 token 请求',16,MUTED)
    save('request-stack','一条档案问答：执行与准备分开观察',b)

    b = text(30,90,'3 份序列 × 512 个位置 × 2048 个数',23,BLUE)
    for i in range(3):
        b += rect(80+i*18,138+i*18,340,120,'#f2f4f0',BLUE)
    b += text(180,265,'[3, 512, 2048]',20) + arrow(470,210,560,210)
    b += text(590,160,'3,145,728 个元素',23) + text(590,215,'BF16：× 2 bytes = 6 MiB',20,BLUE)
    b += text(590,260,'FP32：× 4 bytes = 12 MiB',20,RUST)
    b += text(35,350,'形状决定数量；类型决定每元素空间。这里只计算一份 tensor。',19)
    save('tensor-shape','先数位置，再换算存储',b,390)

    b = arrow(100,340,890,340,INK)+arrow(100,340,100,80,INK)
    b += line(100,340,490,150,BLUE) + line(490,150,880,150,BLUE)
    b += text(740,130,'64 TFLOP/s',19,BLUE) + text(300,90,'带宽 0.8 TB/s',18,MUTED)
    b += text(520,380,'算术强度 FLOP/byte',18) + text(35,75,'性能',17)
    for x,y,label in [(198,292,'20 → 上限 16'),(710,150,'160 → 上限 64')]:
        b += f'<circle cx="{x}" cy="{y}" r="7" fill="{RUST}"/>' + text(x+12,y-12,label,18,RUST)
    b += line(490,150,490,340,LINE,True) + text(475,365,'80',16)
    b += text(115,420,'假设设备；上界取 min(计算峰值, 带宽 × 强度)，并非实测曲线。',17,MUTED)
    save('roofline','两个工作点，共用同一条性能天花板',b,460)

    b = ''
    for y,label,parts in [(120,'推理',[('权重',230),('KV',220),('工作区',150),('运行时',140)]),
                          (260,'训练',[('参数',120),('梯度',120),('优化器',300),('激活 / 临时',200)])]:
        b += text(30,y+34,label,22)
        x=135
        for i,(label,w) in enumerate(parts):
            b += rect(x,y,w,64,'#e7eef0' if i%2==0 else '#e8e5db')+text(x+12,y+38,label,19)
            x+=w
    b += text(135,220,'请求长度与并发增加 KV；当前执行形状改变工作区。',18,BLUE)
    b += text(135,360,'示意分类，不按比例；训练的长期状态不能靠减少请求并发消除。',17,MUTED)
    save('memory-ledger','同一设备，不同工作有不同内存组成',b,410)

    b=''
    for row,(name,prompt,out) in enumerate([('甲',12,3),('乙',3,9)]):
        y=110+row*135
        b+=text(30,y+30,name,24)
        for i in range(prompt): b+=rect(100+i*32,y,28,48,PALE,BLUE)
        b+=text(100,y-14,f'输入并行组织：{prompt} 个已知位置',18,BLUE)
        start=100+prompt*32+35
        for i in range(out):
            b+=rect(start+i*40,y,28,48,'#eee1d7',RUST)
            if i: b+=arrow(start+(i-1)*40+28,y+25,start+i*40,y+25,RUST)
        b+=text(start,y+80,f'后续 {out} 个位置按依赖推进',17,RUST)
    b+=text(30,405,'格子是位置数，不是等时 GPU 工作；每轮可以混合其他请求。',18,MUTED)
    save('prefill-decode','长输入与长输出：两种不同形状',b,445)

    b=text(30,90,'逻辑块顺序',20)+text(600,90,'物理池中的位置',20)
    for i,dest in enumerate([7,2,9,4]):
        y=110+i*65
        b+=box(70,y,170,48,f'逻辑块 {i}')
        py=110+[2,0,3,1][i]*65
        b+=arrow(240,y+24,595,py+24)
    for j,n in enumerate([2,4,7,9]):b+=box(600,110+j*65,240,48,f'物理块 {n}')
    b+=text(30,415,'块表保存映射，物理地址不需要与逻辑顺序相邻。',18,MUTED)
    save('kv-pages','连续历史，不要求连续物理块',b,455)

    b=text(30,90,'每块 8 槽；颜色区分有效内容与尚未写入的尾槽',19)
    for row,n in enumerate([9,14,20]):
        y=120+row*75
        b+=text(30,y+26,f'{n} 位置',19)
        slots=((n+7)//8)*8
        for k in range(slots):
            x=145+k*27+(k//8)*12
            b+=rect(x,y,23,36,BLUE if k<n else '#f1e5d9',BLUE if k<n else RUST)
        b+=text(840,y+26,f'空 {slots-n}',18,RUST)
    b+=text(30,390,'43 个有效位置 / 56 个分配槽；逻辑内容 1548 KiB，块容量 2016 KiB。',19)
    save('kv-block-budget','尾块浪费：三条序列逐格核算',b,430)

    b=text(160,90,'第 1 轮       第 2 轮       第 3 轮       第 4 轮       第 5 轮',18)
    for row,(name,rounds) in enumerate([('A',[1,1,0,0,0]),('B',[1,1,1,1,1]),('C',[0,1,1,1,0]),('D',[0,0,1,1,1])]):
        y=115+row*53;b+=text(60,y+27,name,22)
        for i,on in enumerate(rounds):
            b+=rect(155+i*135,y,110,37,BLUE if on else '#f2f1eb')
            if on:b+=text(210+i*135,y+26,'执行',17,'white','middle')
    b+=text(60,375,'A 退出后，D 可在下一轮进入；B 不必结束，批次成员就能改变。',18)
    save('continuous-batching','按轮重组，而非整批等待',b,420)

    rows=[('DP','不同请求 / 样本','模型副本','训练梯度同步'),('TP','一层内矩阵片段','同一请求协作','层内结果交换'),
          ('PP','不同层区间','激活依次前进','stage 边界传输'),('CP','不同序列位置','跨位置注意力','注意力信息'),('EP','不同专家','token 按 router 分发','定向收发 / AllToAll')]
    b=''
    for i,h in enumerate(['切分','分给谁','逻辑关系','主要交接']):b+=text([30,150,420,690][i],93,h,18,BLUE)
    for row,items in enumerate(rows):
        y=120+row*55;b+=line(30,y+34,930,y+34)
        for x,s in zip([30,150,420,690],items):b+=text(x,y+15,s,18)
    save('parallelism','不同切分，改变不同的数据归属',b,435)

    b=text(30,90,'输入：rank 0 = [2,7]；rank 1 = [5,1]',21)
    for y,title,left,right in [(125,'sum AllReduce','[7,8]','[7,8]'),(195,'AllGather','[2,7,5,1]','[2,7,5,1]'),
                                (265,'ReduceScatter','[7]','[8]'),(335,'AllToAll','[2,5]','[7,1]')]:
        b+=text(30,y+28,title,20)+box(350,y,230,48,left)+box(650,y,230,48,right)
    b+=text(380,420,'rank 0 输出',16,MUTED)+text(680,420,'rank 1 输出',16,MUTED)
    save('collectives','同样输入，四种数据合同',b,460)

    b=text(30,90,'长期状态：按 rank 分片驻留',20)
    for i in range(4):
        x=30+i*120;b+=text(x+12,130,f'rank {i}',18,BLUE)
        for j,label in enumerate(['参数片段','梯度片段','更新历史']):b+=box(x,145+j*57,105,45,label)
    b+=line(525,85,525,380)+text(555,90,'一次 unit 的生命周期',20)
    for i,(label,detail) in enumerate([('收集参数','AllGather'),('执行计算','当前 unit'),('归约梯度','ReduceScatter'),('保留分片','准备下一个 unit')]):
        y=112+i*69;b+=box(580,y,320,59,label,detail)
        if i<3:b+=arrow(740,y+59,740,y+69)
    b+=text(30,425,'分片降低常驻量；收集、预取和临时 buffer 仍可能形成峰值。',18,MUTED)
    save('training-memory','常驻变少，不代表执行峰值等比例缩小',b,465)

    b=''
    steps=[('设备发现','驱动 / 健康',40,105),('资源报告','插件 → kubelet',270,105),
           ('节点绑定','scheduler',500,105),('设备暴露','kubelet / runtime',730,105)]
    for label,detail,x,y in steps:b+=box(x,y,190,76,label,detail)
    for x in [230,460,690]:b+=arrow(x,143,x+35,143)
    for x,title,detail in [(40,'节点无资源','查注册和健康'),(350,'Pod Pending','查数量与约束'),(660,'容器内不可见','查分配与运行时')]:
        b+=box(x,255,260,76,title,detail,'#eee8dd')
    b+=text(40,395,'整数量可分配 ≠ 显存足够 ≠ 多 rank 已就绪。',20,RUST)
    save('k8s-gpu','资源声明到实际访问：按阶段定位',b)

    b=box(30,105,175,90,'接入与边界','模型、租户、长度')+arrow(205,150,255,150)
    b+=box(260,85,230,70,'模型 A 就绪组','新请求只到 Ready')+box(260,190,230,70,'模型 B 就绪组','独立容量合同')
    b+=box(620,85,290,70,'旧版本排空组','不接新工作，处理已有流')
    b+=line(490,120,615,120,MUTED,True)+text(520,185,'版本切换',16,MUTED)
    for i,(t,d) in enumerate([('下载','限制同时准备数'),('加载 / 预热','端口开放还不够'),('就绪','才计入可服务容量')]):
        b+=box(60+i*300,315,260,65,t,d)
        if i<2:b+=arrow(320+i*300,347,355+i*300,347)
    b+=text(30,430,'准备链不能即时吸收突发；等待队列必须有长度与时限边界。',18,RUST)
    save('serving-cluster','流量选择与容量准备是两条链',b,470)

    b=''
    segments=[('接入',12),('等待',78),('输入执行',65),('生成',480),('末段回传',25)]
    for i,(label,ms) in enumerate(segments):
        y=105+i*49; start=sum(x[1] for x in segments[:i]); x=190+start*.9
        b+=text(30,y+25,label,18)+rect(x,y,max(ms*.9,5),30,BLUE if i%2==0 else RUST)
        b+=text(x+max(ms*.9,5)+10,y+23,f'{ms} ms',16)
    b+=line(190,365,800,365)+text(190,390,'0',16)+text(784,390,'660 ms',16)
    b+=text(30,435,'首字边界与客户端收到时间需按测量口径定义；末段回传不能算作模型执行。',17,MUTED)
    save('latency-waterfall','一条请求的阶段耗时，不能只看总长',b,475)

    b=box(350,85,260,65,'检测异常','保留首错与阶段')
    for x,title,detail in [(30,'请求边界','拒绝 / 明确结束'),(270,'协作组失败','重建一致参与者'),(510,'设备异常','隔离、诊断、验证'),(750,'保存不完整','回退已提交版本')]:
        b+=arrow(480,150,x+90,225)+box(x,225,180,90,title,detail)
    b+=text(40,390,'恢复完成条件：可继续正确执行、资源已清理、状态可再次保存。',19)
    b+=text(40,425,'Pod 重建只恢复组件存在，不自动重放业务结果。',18,RUST)
    save('failure-loop','分类后恢复，不把所有失败都交给重启',b,465)


if __name__ == '__main__':
    render()
    assert len(list(OUT.glob('*.svg'))) == 15
    import xml.etree.ElementTree as ET
    for file in OUT.glob('*.svg'):
        ET.fromstring(file.read_text())
    print('Rendered and parsed 15 authored SVG diagrams')
