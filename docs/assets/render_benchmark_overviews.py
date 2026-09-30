"""Render the updated demo's radar and bars from the frozen website_chart_data.json.

Requires matplotlib and numpy. Defaults to report PDFs/PNGs; --language zh
and --font enable Chinese labels. --output-dir and --suffix serve web assets.
The source retains exact displayed bar values, including website aggregates.
"""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from matplotlib.font_manager import FontProperties
import numpy as np

PINK, ROSE, BLUE, GREEN, PURPLE = '#c42d54','#e45b81','#007dab','#138366','#8554bd'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--language',choices=['en','zh'],default='en')
parser.add_argument('--font')
parser.add_argument('--output-dir',type=Path,default=Path(__file__).resolve().parent)
parser.add_argument('--suffix',default='')
args=parser.parse_args();OUT=args.output_dir;OUT.mkdir(parents=True,exist_ok=True)
DATA=json.loads((Path(__file__).resolve().parent/'website_chart_data.json').read_text())
ZH=args.language=='zh';FONT=FontProperties(fname=args.font) if args.font else FontProperties(family='DejaVu Sans')
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'pdf.fonttype':42,'svg.fonttype':'path','svg.hashsalt':'index-translate-20260930','axes.spines.top':False,'axes.spines.right':False})
RECORDS=[]
def tr(en,zh):return zh if ZH else en

def save(fig,name):
 if name=='benchmark_radar' and args.suffix:name='benchmark-radar'
 for ext in ['pdf','png','svg']:
  target=OUT/(name+args.suffix+'.'+ext)
  meta={'CreationDate':None,'ModDate':None} if ext=='pdf' else {'Date':None} if ext=='svg' else {}
  fig.savefig(target,dpi=190,bbox_inches='tight',pad_inches=.10,facecolor='white',metadata=meta)
  if ext=='svg':target.write_text('\n'.join(x.rstrip() for x in target.read_text().splitlines())+'\n')
 plt.close(fig)

def vals(i,offset=0,step=1):return [b['value'] for b in DATA['charts'][i]['bars']][offset::step]

def horizontal(ax,labels,values,colors,title,limit=1,fmt='.4f',percent=False):
 RECORDS.append({'metric':title,'models':labels,'values':values,'axis_min':0,'axis_max':limit})
 yy=np.arange(len(labels));ax.barh(yy,values,height=.60,color=colors,zorder=3)
 ax.set_yticks(yy,labels,fontsize=9);ax.invert_yaxis();ax.set_xlim(0,limit)
 ax.set_xticks(np.linspace(0,limit,5));ax.tick_params(axis='both',length=0,labelsize=8)
 ax.grid(axis='x',color='#e1e5eb',linewidth=.6,zorder=0);ax.spines[['left','bottom']].set_visible(False)
 ax.set_title(title,loc='left',fontsize=10.5,pad=10,fontproperties=FONT)
 for y,v in zip(yy,values):
  ax.text(min(v+limit*.014,limit*.985),y,format(v,fmt)+('%' if percent else ''),va='center',ha='left' if v<limit*.91 else 'right',fontsize=8.5,color='#273142')

def radar():
 d=DATA['radar'];scores={m['name']:np.array(m['values']) for m in d['models']}
 lo=np.array([r['min'] for r in d['ranges']]);hi=np.array([r['max'] for r in d['ranges']])
 baseline=np.max([v for k,v in scores.items() if not k.startswith('Index-')],axis=0)
 series=[('Index-Translate-35B-A3B\n(preview)',scores['Index-Translate-35B-A3B'],PINK,'-'),('Index-Translate-9B',scores['Index-Translate-9B'],ROSE,'-'),('Index-Translate-2B',scores['Index-Translate-2B'],BLUE,'--'),('DeepSeek-V4.1-Flash',scores['deepseek_v4.1_flash'],GREEN,'-'),('GPT-5.6-Sol',scores['gpt-5.6-sol'],PURPLE,'-'),(tr('Best non-Index\n(per category)','非 Index 最优（逐维）'),baseline,'#454f60','--')]
 theta=np.pi/2-np.arange(7)*2*np.pi/7;unit=np.stack([np.cos(theta),np.sin(theta)],axis=1)
 fig=plt.figure(figsize=(8.5,4.05));ax=fig.add_axes([.035,.045,.62,.88])
 for level in [.25,.5,.75,1]:
  ax.add_patch(Polygon(unit*level,closed=True,fill=False,edgecolor='#dce2ea',linewidth=.75));ax.text(.035,level,str(int(level*100)),fontsize=7,color='#7a8695')
 for u in unit:ax.plot([0,u[0]],[0,u[1]],color='#e3e7ed',lw=.7)
 labels=tr(['WMT','FLORES','Instruction\nfollowing','Low-resource','Subtitles','MEME','Books / fiction'],['WMT','FLORES','指令遵循','小语种','字幕翻译','MEME','书籍网文'])
 for label,u in zip(labels,unit):ax.text(*(u*1.17),label,va='center',ha='left' if u[0]>.25 else 'right' if u[0]<-.25 else 'center',fontsize=9.1,color='#273142',fontproperties=FONT)
 handles=[]
 for i,(name,values,color,style) in enumerate(series):
  norm=(values-lo)/(hi-lo);points=np.vstack([unit*norm[:,None],unit[0]*norm[0]])
  if i<3:ax.fill(points[:,0],points[:,1],color=color,alpha=.035)
  line,=ax.plot(points[:,0],points[:,1],color=color,linewidth=1.9 if i<3 else 1.25,linestyle=style,marker='o' if i<3 else None,markersize=3,zorder=8-i,label=name);handles.append(line)
 ax.set_aspect('equal');ax.set_xlim(-1.6,1.6);ax.set_ylim(-1.15,1.22);ax.axis('off')
 fig.legend(handles,[s[0] for s in series],loc='center left',bbox_to_anchor=(.70,.51),frameon=False,prop=FontProperties(fname=args.font,size=8.4) if args.font else FontProperties(size=8.4),labelspacing=1.15,handlelength=2.3)
 save(fig,'benchmark_radar')

radar()
labels=['Index 35B-A3B*','Index 9B','Index 2B','Hy-MT2 30B-A3B','GPT-5.6-Sol','Gemini 3.5 Flash Lite'];colors=[PINK,ROSE,BLUE,'#598b3d',PURPLE,'#8b8b8b']
specs=[(0,0,2,tr('FLORES / COMET-22 ↑','FLORES / COMET-22 ↑')),(0,1,2,tr('WMT24++ / COMET-22 ↑','WMT24++ / COMET-22 ↑')),(1,0,2,tr('Instruction / mean Quality score ↑','指令翻译 / Quality score 均值 ↑')),(1,1,2,tr('Instruction / mean IFscore ↑','指令遵循 / IFscore 均值 ↑')),(2,0,1,tr('Five-domain mean / COMET-22 ↑','五项垂类均值 / COMET-22 ↑')),(3,0,1,tr('MEME / quality ↑','MEME / 翻译质量 ↑')),(4,0,2,tr('FLORES_minor_pair / COMET-22 ↑','FLORES_minor_pair / COMET-22 ↑')),(4,1,2,tr('instTrans_minor / IFscore ↑','instTrans_minor / IFscore ↑'))]
fig,axes=plt.subplots(4,2,figsize=(9.7,8.3));fig.subplots_adjust(left=.17,right=.98,top=.96,bottom=.035,wspace=1.03,hspace=.58)
for ax,(i,o,s,title) in zip(axes.flat,specs):horizontal(ax,labels,vals(i,o,s),colors,title)
save(fig,'text_benchmark_overview')
# Separate cards keep the demo's MEME and low-resource views reusable in articles.
for name,indices in [('meme_benchmark_overview',[5]),('minor_benchmark_overview',[6,7])]:
 fig,axes=plt.subplots(1,len(indices),figsize=(5.2 if len(indices)==1 else 9.7,2.8));fig.subplots_adjust(left=.31 if len(indices)==1 else .17,right=.97,top=.84,bottom=.13,wspace=1.03)
 for ax,j in zip(np.atleast_1d(axes),indices):
  i,o,s,title=specs[j];horizontal(ax,labels,vals(i,o,s),colors,title)
 save(fig,name)
# Echo: preserve the demo's deployed S2ST comparison, separate from the six-direction matched study.
fig=plt.figure(figsize=(9.7,4.9));grid=fig.add_gridspec(2,2,left=.20,right=.98,top=.94,bottom=.15,hspace=.77,wspace=.43)
ax=fig.add_subplot(grid[0,:]);horizontal(ax,['Index-Echo-9B','Index-Echo-2B','Gemini 3.1 Pro (thinking)','FireRed Audio'],vals(5),[ROSE,BLUE,PURPLE,'#9aa5b2'],tr('S2TT / MT judge ↑','语音到文字 / MT judge ↑'),fmt='.3f')
for j,chart in enumerate([6,7]):
 ax=fig.add_subplot(grid[1,j]);x=np.arange(3);w=.23
 for k,(name,color) in enumerate([('Index-Echo-2B',BLUE),('Pipeline','#598b3d'),('SeamlessM4T-v2','#9aa5b2')]):
  v=vals(chart,k,3);bar=ax.bar(x+(k-1)*w,v,width=w,color=color,label=name,zorder=3);ax.bar_label(bar,labels=[f'{z:.3f}' for z in v],fontsize=7.5,padding=3,rotation=90)
  RECORDS.append({'metric':DATA['charts'][chart]['title'],'models':[name+' '+s for s in ['EN','ES','JA']],'values':v,'axis_min':0,'axis_max':.6 if chart==6 else 1})
 ax.set_xticks(x,['EN WER','ES WER','JA CER'] if chart==6 else ['EN','ES','JA'],fontsize=8)
 ax.set_ylim(0,.6 if chart==6 else 1);ax.grid(axis='y',color='#e1e5eb',lw=.6,zorder=0);ax.spines[['left','bottom']].set_visible(False);ax.tick_params(length=0,labelsize=8)
 ax.set_title(tr('S2ST / content error ↓','语音到语音 / 内容错误率 ↓') if chart==6 else tr('S2ST / speaker cosine ↑','语音到语音 / 音色相似度 ↑'),loc='left',fontproperties=FONT,fontsize=10.5,pad=12)
 if j==0:handles,leg=ax.get_legend_handles_labels()
fig.legend(handles,leg,loc='lower center',bbox_to_anchor=(.55,.0),ncol=3,frameon=False,fontsize=8)
save(fig,'echo_benchmark_overview')
labels=['Index-Homura 9B','Hy-MT2 7B','Hy-MT2 30B-A3B','Qwen3.5 9B'];colors=[ROSE,'#a57126','#598b3d','#5473bd']
fig,axes=plt.subplots(1,2,figsize=(9.7,2.55));fig.subplots_adjust(left=.17,right=.98,top=.79,bottom=.13,wspace=.90)
horizontal(axes[0],labels,vals(8),colors,tr('SandGlass / overall score ↑','SandGlass / 综合分 ↑'))
horizontal(axes[1],labels,vals(9),colors,tr('Within 10% of target syllables ↑','音节偏差不超过 10% 的比例 ↑'),100,'.2f',True)
save(fig,'homura_benchmark_overview')
labels=['Index-NativeLong 9B','North-Small-Translate','Qwen3.8 Flash','Hy-MT2 30B-A3B'];colors=[ROSE,'#7466a3','#5473bd','#598b3d']
fig,axes=plt.subplots(1,2,figsize=(9.7,2.55));fig.subplots_adjust(left=.18,right=.98,top=.79,bottom=.13,wspace=1.03)
for ax,i,title in zip(axes,[10,11],['GuoFeng / 64K tokens ↑','BWB Track A3 / 64K tokens ↑']):horizontal(ax,labels,vals(i),colors,title)
save(fig,'nativelong_benchmark_overview')
(OUT/('benchmark_overview_values'+args.suffix+'.json')).write_text(json.dumps(RECORDS,ensure_ascii=False,indent=2)+'\n')
print('Rendered latest 14-model radar and all 12 demo bar charts:',OUT)
