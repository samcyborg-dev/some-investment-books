"""Typeset the original ORB research manuscript into a standalone, bookmarked PDF.

Uses ReportLab and Matplotlib's bundled DejaVu fonts. No network or trading calls.
Pages are explicitly measured before rendering: oversized content fails the build.
"""
from pathlib import Path
from html import escape
import importlib.metadata
import json
import re
import hashlib
import platform

import matplotlib
from PIL import Image as PILImage
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Table, TableStyle, Image, Spacer

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/'STRATEGY_1_ORB_FORENSIC_RESEARCH.pdf'
W,H=A4
M=48
CW=W-2*M
TOP=H-60
BOTTOM=53
NAVY=colors.HexColor('#162b43')
TEAL=colors.HexColor('#117c83')
GRAY=colors.HexColor('#526376')
LIGHT=colors.HexColor('#edf4f6')
GOLD=colors.HexColor('#be9145')
CORAL=colors.HexColor('#a94d3e')

font_dir=Path(matplotlib.get_data_path())/'fonts'/'ttf'
for name,file in [('Body','DejaVuSans.ttf'),('BodyBold','DejaVuSans-Bold.ttf'),
                  ('BodyItalic','DejaVuSans-Oblique.ttf'),('BodyBoldItalic','DejaVuSans-BoldOblique.ttf'),
                  ('Serif','DejaVuSerif.ttf'),('SerifBold','DejaVuSerif-Bold.ttf'),
                  ('Mono','DejaVuSansMono.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(font_dir/file)))
pdfmetrics.registerFontFamily('Body',normal='Body',bold='BodyBold',italic='BodyItalic',boldItalic='BodyBoldItalic')


def inline(s):
    # Escape user prose first; only known Markdown constructs become PDF markup.
    links=[]
    def hold(m):
        label,url=m.groups()
        links.append(f'<link href="{escape(url,quote=True)}" color="#117c83">{escape(label)}</link>')
        return f'LINKTOKEN{len(links)-1}TOKENEND'
    s=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',hold,s)
    s=escape(s)
    s=re.sub(r'`([^`]+)`',r'<font name="Mono" size="8.4">\1</font>',s)
    s=re.sub(r'\*\*([^*]+)\*\*',r'<b>\1</b>',s)
    s=re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)',r'<i>\1</i>',s)
    for i,link in enumerate(links):s=s.replace(f'LINKTOKEN{i}TOKENEND',link)
    return s


def styles(scale=1.):
    return {
      'kicker':ParagraphStyle('Kicker',fontName='BodyBold',fontSize=8.0,leading=11,textColor=TEAL,spaceAfter=10),
      'h1':ParagraphStyle('Title',fontName='SerifBold',fontSize=23.5,leading=28.5,textColor=NAVY,spaceAfter=16),
      'h2':ParagraphStyle('Subhead',fontName='BodyBold',fontSize=11.1*scale,leading=15*scale,textColor=TEAL,spaceBefore=7*scale,spaceAfter=7*scale),
      'body':ParagraphStyle('Body',fontName='Body',fontSize=10.05*scale,leading=14.15*scale,textColor=NAVY,spaceAfter=10*scale,splitLongWords=True),
      'bullet':ParagraphStyle('Bullet',fontName='Body',fontSize=9.9*scale,leading=14*scale,textColor=NAVY,leftIndent=12,firstLineIndent=-9,spaceAfter=8*scale),
      'caption':ParagraphStyle('Caption',fontName='BodyItalic',fontSize=8.15*scale,leading=11.3*scale,textColor=GRAY,spaceAfter=10*scale),
      'table':ParagraphStyle('Cell',fontName='Body',fontSize=8.75*scale,leading=12.05*scale,textColor=NAVY,splitLongWords=True),
      'th':ParagraphStyle('CellHeader',fontName='BodyBold',fontSize=8.5*scale,leading=11.7*scale,textColor=colors.white,splitLongWords=True),
      'formula':ParagraphStyle('Formula',fontName='Mono',fontSize=9.0*scale,leading=14*scale,textColor=NAVY),
      'callout':ParagraphStyle('Callout',fontName='Body',fontSize=9.25*scale,leading=13.2*scale,textColor=NAVY),
      'toc':ParagraphStyle('TOC',fontName='Body',fontSize=9.2*scale,leading=12.5*scale,textColor=NAVY),
    }


def read_pages():
    text=(HERE/'report.md').read_text()
    parts=re.split(r'<!-- PAGE (.*?) -->',text)
    pages=[]
    for i in range(1,len(parts),2):
        ident,kicker,title=[x.strip() for x in parts[i].split('|')]
        pages.append({'id':ident,'kicker':kicker,'title':title,'body':parts[i+1].strip(),'page':len(pages)+1})
    return pages


def table_widths(rows):
    n=len(rows[0])
    head=' '.join(rows[0]).lower()
    if n==2:
        return [CW*.32,CW*.68]
    if n==3:
        if 'location' in head or 'evidence' in head:return [CW*.25,CW*.31,CW*.44]
        if 'definition' in head:return [CW*.21,CW*.43,CW*.36]
        return [CW*.29,CW*.345,CW*.365]
    if n==4:
        if 'candidate state' in head:return [CW*.20,CW*.28,CW*.24,CW*.28]
        if 'scenario' in head:return [CW*.43,CW*.19,CW*.19,CW*.19]
        if 'model' in head:return [CW*.48,CW*.18,CW*.18,CW*.16]
        return [CW*.36,CW*.23,CW*.21,CW*.20]
    if n==5:return [CW*.38,CW*.16,CW*.15,CW*.15,CW*.16]
    if n==6:
        if 'episode' in head:return [CW*.10,CW*.19,CW*.19,CW*.19,CW*.12,CW*.21]
        return [CW*.27,CW*.145,CW*.17,CW*.145,CW*.135,CW*.135]
    return [CW/n]*n


def make_table(raw,st,scale):
    rows=[]
    for line in raw:
        r=[x.strip() for x in line.strip().strip('|').split('|')]
        if all(re.fullmatch(r'[:\- ]+',x) for x in r):continue
        rows.append(r)
    if len({len(r) for r in rows})!=1:raise ValueError('Irregular table '+str(rows))
    cells=[[Paragraph(inline(s),st['th'] if i==0 else st['table']) for s in r] for i,r in enumerate(rows)]
    t=Table(cells,colWidths=table_widths(rows),hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),NAVY),('VALIGN',(0,0),(-1,-1),'TOP'),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#f0f4f7'),colors.white]),
        ('LINEBELOW',(0,0),(-1,0),.6,TEAL),
        ('LINEBELOW',(0,1),(-1,-1),.35,colors.HexColor('#dce4ea')),
        ('LEFTPADDING',(0,0),(-1,-1),7*scale),('RIGHTPADDING',(0,0),(-1,-1),7*scale),
        ('TOPPADDING',(0,0),(-1,-1),6*scale),('BOTTOMPADDING',(0,0),(-1,-1),6*scale)
    ]))
    return [t,Spacer(1,11*scale)]


def toc(pages,st):
    index={p['id']:p['page'] for p in pages}
    rows=[('corrections','01  Evidence reset','corrections'),
          ('meaning','02  Meaning, mechanism and mathematics','math'),
          ('rulebook','03  Rules, clocks, orders, exits and sizing','sizing'),
          ('long','04  Worked long, short and failed breakouts','failed'),
          ('evidence','05  SSRN forensic case studies and counterevidence','contrary'),
          ('regimes','06  Favorable conditions and failure regimes','failures'),
          ('dd-definitions','07  Drawdown periods, streaks and prop constraints','challenge'),
          ('trade-metrics','08  Metrics, confidence and selection bias','inference'),
          ('parameters','09  Parameter sensitivity and illustrative stress lab','lab-stress'),
          ('audit-execution','10  Local execution, accounting and simulation audit','audit-statistics'),
          ('validation','11  Validation, operations and trading journal','journal'),
          ('pine','12  Pine Script handoff and decision record','decision'),
          ('refs-a','     Source register with access limits','refs-d'),
          ('reproducibility','     Reproducibility appendix','reproducibility')]
    cells=[]
    for key,title,end in rows:
        page=index[key];last=index[end];num=str(page) if page==last else f'{page}–{last}'
        cells.append([Paragraph(f'<link href="#{key}" color="#162b43">{escape(title)}</link>',st['toc']),
                      Paragraph(f'<link href="#{key}" color="#117c83"><b>{num}</b></link>',st['toc'])])
    t=Table(cells,colWidths=[CW-45,45])
    t.setStyle(TableStyle([('LINEBELOW',(0,0),(-1,-1),.35,colors.HexColor('#dce4ea')),
                          ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),1),
                          ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
    return [t,Spacer(1,10)]


def parse(page,pages,scale=1.):
    st=styles(scale)
    lines=page['body'].splitlines()
    items=[Paragraph(escape(page['kicker']),st['kicker'])]
    i=0
    while i<len(lines):
        line=lines[i].strip()
        if not line:i+=1;continue
        if line=='{{TOC}}':items.extend(toc(pages,st));i+=1;continue
        if line.startswith('# '):items.append(Paragraph(inline(line[2:]),st['h1']));i+=1;continue
        if line.startswith('## '):items.append(Paragraph(inline(line[3:]),st['h2']));i+=1;continue
        if line.startswith('|'):
            raw=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                raw.append(lines[i]);i+=1
            items.extend(make_table(raw,st,scale));continue
        if line==':::formula':
            text=[];i+=1
            while i<len(lines) and lines[i].strip()!=':::':text.append(lines[i]);i+=1
            i+=1
            pars=[Paragraph(escape(x),st['formula']) for x in text]
            t=Table([[pars]],colWidths=[CW]);t.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,-1),LIGHT),('BOX',(0,0),(-1,-1),.5,colors.HexColor('#c5dfe2')),
                ('LEFTPADDING',(0,0),(-1,-1),11),('RIGHTPADDING',(0,0),(-1,-1),11),
                ('TOPPADDING',(0,0),(-1,-1),10*scale),('BOTTOMPADDING',(0,0),(-1,-1),10*scale)]))
            items.extend([t,Spacer(1,12*scale)]);continue
        m=re.fullmatch(r'!\[([^\]]+)\]\(([^)]+)\)',line)
        if m:
            path=HERE/m.group(2)
            iw,ih=PILImage.open(path).size
            ratio=min(CW/iw,198*scale/ih)
            im=Image(str(path),width=iw*ratio,height=ih*ratio);im.hAlign='CENTER'
            # Canvas-drawn flowables don't implement hAlign, so draw wrapper uses offset.
            im._center=True
            items.extend([im,Spacer(1,7*scale)]);i+=1;continue
        if line.startswith('> '):
            text=line[2:]
            if ' | ' in text:
                label,body=text.split(' | ',1);text=f'**{label}**<br/>'+body
                rendered=inline(text).replace('&lt;br/&gt;','<br/>')
            else:rendered=inline(text)
            t=Table([[Paragraph(rendered,st['callout'])]],colWidths=[CW])
            t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#f7f2e8')),
                                  ('LINEBEFORE',(0,0),(0,-1),3,GOLD),
                                  ('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),11),
                                  ('TOPPADDING',(0,0),(-1,-1),10*scale),('BOTTOMPADDING',(0,0),(-1,-1),10*scale)]))
            items.extend([t,Spacer(1,8*scale)]);i+=1;continue
        if line.startswith('- '):
            items.append(Paragraph('•  '+inline(line[2:]),st['bullet']));i+=1;continue
        if re.match(r'^\d+\. ',line):
            items.append(Paragraph(inline(line),st['body']));i+=1;continue
        if line.startswith('*') and line.endswith('*') and not line.startswith('**'):
            items.append(Paragraph(inline(line[1:-1]),st['caption']));i+=1;continue
        buf=[line];i+=1
        while i<len(lines) and lines[i].strip() and not re.match(r'^(#|\||!\[|>|- |:::|\{\{)',lines[i].strip()):
            buf.append(lines[i].strip());i+=1
        items.append(Paragraph(inline(' '.join(buf)),st['body']))
    return items


def dimensions(items):
    measure=[]
    for item in items:
        w,h=item.wrap(CW,10000)
        before=item.getSpaceBefore();after=item.getSpaceAfter()
        measure.append((item,w,h,before,after))
    return measure,sum(h+b+a for _,w,h,b,a in measure)


def running(c,page,total):
    c.setFillColor(NAVY);c.setFont('BodyBold',7.6)
    c.drawString(M,H-29,'QUANT RESEARCH  /  STRATEGY 01')
    c.setFont('Body',7.5);c.setFillColor(GRAY)
    c.drawRightString(W-M,H-29,'OPENING RANGE BREAKOUT')
    c.setStrokeColor(colors.HexColor('#d4dee5'));c.setLineWidth(.6);c.line(M,H-38,W-M,H-38)
    c.setStrokeColor(colors.HexColor('#d4dee5'));c.line(M,42,W-M,42)
    c.setFillColor(GRAY);c.setFont('Body',7.2)
    c.drawString(M,27,'RESEARCH ONLY  ·  08 SEP 2026')
    c.setFillColor(TEAL);c.drawCentredString(W/2,27,'CONTENTS')
    c.linkRect('', 'contents', (W/2-25,23,W/2+25,35), relative=0, thickness=0)
    c.setFillColor(NAVY);c.setFont('BodyBold',8)
    c.drawRightString(W-M,26,f'{page:02d} / {total:02d}')


def cover(c,total):
    c.setFillColor(NAVY);c.rect(0,0,W,H,fill=1,stroke=0)
    c.setFillColor(TEAL);c.rect(0,0,13,H,fill=1,stroke=0)
    c.setStrokeColor(colors.HexColor('#24475d'))
    for x in range(46,int(W),36):c.line(x,120,x,400)
    for y in range(135,411,35):c.line(46,y,W-45,y)
    # Geometric opening range and stylized upward escape; decoration, no market scale.
    c.setFillColor(colors.HexColor('#1d3b50'));c.rect(54,219,267,110,fill=1,stroke=0)
    c.setStrokeColor(colors.HexColor('#3d7585'));c.setLineWidth(1)
    c.setDash(4,4);c.line(54,329,W-45,329);c.line(54,219,W-45,219);c.setDash()
    p=c.beginPath();pts=[(55,262),(88,300),(120,253),(151,276),(183,233),(214,311),(246,290),(279,303),(313,322),(346,368),(378,345),(411,387),(444,375),(483,412),(526,443)]
    p.moveTo(*pts[0])
    for xy in pts[1:]:p.lineTo(*xy)
    c.setStrokeColor(colors.HexColor('#6bbec1'));c.setLineWidth(2.4);c.drawPath(p)
    c.setFillColor(colors.HexColor('#acd8da'));c.setFont('BodyBold',10)
    c.drawString(54,H-67,'STRATEGY 01  /  FORENSIC RESEARCH DOSSIER')
    c.setFillColor(colors.white);c.setFont('BodyBold',43)
    c.drawString(50,H-143,'OPENING RANGE')
    c.drawString(50,H-195,'BREAKOUT')
    c.setFont('Serif',20);c.setFillColor(colors.HexColor('#d8e8ef'))
    c.drawString(54,H-242,'The evidence behind the setup.')
    c.setFont('Body',11.1)
    for j,line in enumerate(['Meaning · Mechanics · Market regimes','Drawdown periods · Metrics · SSRN forensics',
                             'Execution risk · Validation · Pine Script handoff']):
        c.drawString(54,H-285-j*20,line)
    c.setFillColor(GOLD);c.setFont('BodyBold',9)
    c.drawString(54,192,'ES / MES RESEARCH FOCUS  ·  30-MINUTE OPENING RANGE')
    c.setFillColor(colors.HexColor('#d8e8ef'));c.setFont('Body',9)
    c.drawString(54,166,'Original critical synthesis. Published results are not live promises.')
    c.drawString(54,148,'Earlier synthetic performance claims are corrected in this report.')
    c.setStrokeColor(colors.HexColor('#557182'));c.setLineWidth(.7);c.line(54,115,W-48,115)
    c.setFillColor(colors.white);c.setFont('BodyBold',10)
    c.drawString(54,87,'08 SEPTEMBER 2026')
    c.setFont('Body',9);c.drawRightString(W-48,87,f'VERSION 1.0  /  {total} PAGES')
    c.setFillColor(colors.HexColor('#acd8da'));c.setFont('Body',8.8)
    c.drawString(54,64,'PDF FIRST. PINE SCRIPT LATER.')


def build():
    pages=read_pages()
    layouts=[];ready=[]
    for p in pages[1:]:
        # Small opt-in typographic compression allowed only within a readable range.
        # Fixed content pages prevent deceptive padding or accidental spillover.
        for scale in [1.0,.98,.96,.94,.92]:
            items=parse(p,pages,scale)
            measured,used=dimensions(items)
            if used<=TOP-BOTTOM:break
        else:
            raise ValueError(f'Page {p["page"]} {p["id"]} needs {used:.1f} pt, max {TOP-BOTTOM:.1f}. Edit content/layout.')
        ready.append((p,measured,used,scale))
        layouts.append({'page':p['page'],'id':p['id'],'used_points':round(used,2),'available_points':round(TOP-BOTTOM,2),
                        'body_font_pt':round(10.05*scale,3),'scale':scale})
    c=canvas.Canvas(str(OUT),pagesize=A4,pageCompression=1,invariant=1)
    c.setTitle('Opening Range Breakout — Strategy 1 Forensic Research Dossier')
    c.setAuthor('Quant Research | Original synthesis for some-investment-books')
    c.setSubject('Critical SSRN research, ORB mechanics, drawdowns, metrics, execution audit and validation plan. Research only.')
    c.setKeywords('ORB, opening range breakout, SSRN, ES, MES, drawdown, research, synthetic performance correction')
    c.bookmarkPage('cover');c.addOutlineEntry('Opening Range Breakout — Research Dossier','cover',0)
    cover(c,len(pages));c.showPage()
    for p,measured,used,scale in ready:
        c.bookmarkPage(p['id']);c.addOutlineEntry(f'{p["page"]:02d}  {p["title"]}',p['id'],0)
        running(c,p['page'],len(pages))
        y=TOP
        for item,w,h,before,after in measured:
            y-=before+h
            x=M+(CW-w)/2 if getattr(item,'_center',False) else M
            item.drawOn(c,x,y)
            y-=after
        assert y>=BOTTOM-.1,(p['id'],y)
        c.showPage()
    c.save()
    metadata={'date':'2026-09-08','output':OUT.name,'page_count':len(pages),
              'python':platform.python_version(),'layout':layouts,
              'dependencies':{m:importlib.metadata.version(m) for m in ['reportlab','pillow','numpy','matplotlib','pandas','pymupdf']},
              'sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in [OUT,HERE/'report.md',HERE/'sources.json',HERE/'calculate_examples.py',
                                  HERE/'illustrative_results.json',HERE/'build_pdf.py',HERE/'test_research.py']}}
    (HERE/'build_metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(f'Built {OUT.name}: {len(pages)} pages, {OUT.stat().st_size/1024:.0f} KiB')
    for lay in layouts:
        print(f"{lay['page']:02d} {lay['id']:<23} {lay['used_points']:6.1f}/{lay['available_points']:.1f} pt; body {lay['body_font_pt']:.2f} pt")

if __name__=='__main__':build()
