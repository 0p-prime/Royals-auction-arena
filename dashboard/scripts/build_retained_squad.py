import csv,json,argparse
from pathlib import Path
ap=argparse.ArgumentParser(description='Project verified historical pressure scores onto the official 18 Nov 2026 RR retained squad.')
ap.add_argument('--model-dir',required=True,help='Directory containing batting_Historical_Scores_filtered.csv and bowling_Historical_Scores_filtered.csv')
ap.add_argument('--out',default='web/retained-squad.json')
args=ap.parse_args()
base=Path(args.out).parent
# Display names and roles match the official RR roster, verified 18 November 2026.
roster=[
('Riyan Parag','All-rounder','India','R Parag',True),
('Yashasvi Jaiswal','Batter','India','YBK Jaiswal',False),
('Vaibhav Sooryavanshi','Batter','India','V Suryavanshi',False),
('Ravindra Jadeja','All-rounder','India','RA Jadeja',False),
('Dhruv Jurel','Wicket-keeper','India','Dhruv Jurel',False),
('Jofra Archer','Bowler','England','JC Archer',False),
('Aman Rao Perala','Batter','India',None,False),
('Brijesh Sharma','All-rounder','India','Brijesh Sharma',False),
('Nandre Burger','Bowler','South Africa','N Burger',False),
('Dasun Shanaka','All-rounder','Sri Lanka','MD Shanaka',False),
('Donovan Ferreira','Wicket-keeper','South Africa','D Ferreira',False),
('Lhuan-dre Pretorius','Wicket-keeper','South Africa','LG Pretorius',False),
('Ravi Bishnoi','Bowler','India','Ravi Bishnoi',False),
('Sandeep Sharma','Bowler','India','Sandeep Sharma',False),
('Shubham Dubey','Batter','India','SB Dubey',False),
('Sushant Mishra','Bowler','India','SS Mishra',False),
('Yash Raj Punja','Bowler','India','Yash Raj Punja',False),
('Mohammed Shami','Bowler','India','Mohammed Shami',False),
('Manimaran Siddharth','Bowler','India','M Siddharth',False)]
models={d:{r['player']:r for r in csv.DictReader(open(Path(args.model_dir)/(d+'_Historical_Scores_filtered.csv')))} for d in ['batting','bowling']}
players=[]
for name,role,country,alias,captain in roster:
 p=dict(name=name,role=role,country=country,modelName=alias,captain=captain,status='Traded in' if name in ['Mohammed Shami','Manimaran Siddharth'] else 'Retained')
 for d in models:
  r=models[d].get(alias)
  # A posterior can exist with no observed pressure balls. It is not a performance score.
  p[d]=None
  if r and int(r['HP_legal_balls'])>0:
   p[d]=dict(score=float(r['Score']),low=float(r['Score80low_conditional_mixture']),high=float(r['Score80high_conditional_mixture']),balls=int(r['HP_legal_balls']),matches=int(r['HP_matches']),provisional=r['eligible'].lower()!='true',shortlist=int(r['HP_legal_balls']) >= (550 if d=='batting' else 601))
 players.append(p)
obj=dict(season='IPL 2027',asOf='18 November 2026',sources=[{'label':'Rajasthan Royals announcement','url':'https://www.rajasthanroyals.com/latest-news/ipl-2027-rr-players-retention-list-retained-released'},{'label':'IPL official retention list','url':'https://www.iplt20.com/news/article/tata-ipl-2027-player-retentions-announced'},{'label':'RR player roles','url':'https://www.rajasthanroyals.com/rr-players'}],players=players)
Path(args.out).write_text(json.dumps(obj,indent=2)+'\n')
print(f'Wrote {len(players)} players to {args.out}')
