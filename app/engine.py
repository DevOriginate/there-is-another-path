from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from .models import AssessmentInput, AssessmentResult, PathResult
from .assessment import build_profile, detect_conflicts, confidence_score, clamp

DATA = Path(__file__).parent / 'data' / 'paths.json'

def load_paths() -> Dict[str, Any]:
    return json.loads(DATA.read_text(encoding='utf-8'))

def ratio_match(user: float, required: float) -> float:
    if required <= 0: return 100.0
    if user >= required: return 100.0
    return clamp(user / required * 100.0)

def weighted_average(items: List[Tuple[float,float]], fallback: float = 50.0) -> float:
    total_w = sum(w for _, w in items)
    if total_w <= 0: return fallback
    return sum(v*w for v,w in items) / total_w

def capability_fit(profile: Dict[str,Any], path: Dict[str,Any]) -> Tuple[float,List[str],List[str]]:
    caps = profile['capabilities']; strengths, gaps, rows = [], [], []
    for trait, req in path['capability_requirements'].items():
        weight = path['capability_weights'].get(trait, 0)
        match = ratio_match(caps.get(trait,50), req)
        rows.append((match, weight))
        if caps.get(trait,50) >= req: strengths.append(f'{trait.title()} is at or above the path requirement.')
        elif match < 70: gaps.append(f'{trait.title()} is currently below the preferred starting level for this path.')
    return weighted_average(rows,70), strengths, gaps

def experience_fit(profile: Dict[str,Any], path: Dict[str,Any]) -> float:
    years = profile['meta']['EXPERIENCE_YEARS']; req_years = path.get('experience_required_years',0)
    depth = 100.0 if req_years <= 0 else ratio_match(years, req_years)
    p_tags = set(path.get('experience_tags',[])); u_tags = set(profile.get('experience_tags',[])); matches = len(p_tags & u_tags)
    if not p_tags: tag_score = 100.0
    elif matches >= 3: tag_score = 100.0
    elif matches == 2: tag_score = 85.0
    elif matches == 1: tag_score = 70.0
    else: tag_score = 45.0 if req_years > 0 else 70.0
    if req_years >= 5: return 0.55*depth + 0.45*tag_score
    if req_years > 0: return 0.4*depth + 0.6*tag_score
    return max(70.0, tag_score)

def learning_fit(profile: Dict[str,Any], path: Dict[str,Any]) -> float:
    user = profile['meta']['LEARNING_HORIZON']; req = path['learning_requirement']
    if user >= req: return 100.0
    gap=req-user
    if gap<=15:return 85.0
    if gap<=30:return 65.0
    if gap<=50:return 40.0
    return 15.0

def time_fit(profile: Dict[str,Any], path: Dict[str,Any]) -> float:
    user = profile['meta']['TIME_WEEK']; req = path['min_weekly_time']
    if user >= req: base=100.0
    else:
        r = user/req if req else 1
        base = 80.0 if r>=.75 else 55.0 if r>=.5 else 30.0 if r>=.25 else 10.0
    return 0.7*base + 0.3*learning_fit(profile,path)

def financial_fit(profile: Dict[str,Any], path: Dict[str,Any]) -> float:
    diff = path['capital_required'] - profile['meta']['CAPITAL_LEVEL']
    if diff<=0:return 100.0
    if diff==1:return 75.0
    if diff==2:return 45.0
    return 10.0

def risk_fit(profile: Dict[str,Any], path: Dict[str,Any]) -> float:
    gap=path['risk_level'] - profile['meta']['RISK_TOLERANCE']
    if gap<=0:return 100.0
    if gap<=20:return 80.0
    if gap<=40:return 55.0
    if gap<=60:return 30.0
    return 10.0

def work_style_fit(profile: Dict[str,Any], path: Dict[str,Any]) -> float:
    p=profile['preferences']; targets=path.get('work_style_targets',{}); rows=[]
    for key,target in targets.items():
        if key not in p: continue
        rows.append((clamp(100-abs(p[key]-target)),1))
    remote_pref=p.get('REMOTE',50); remote_compat=path.get('remote_compatibility',50)
    if remote_pref>=70: rows.append((min(100, remote_compat + (100-remote_pref)*0.3),1.5))
    return weighted_average(rows,70)

def goal_fit(profile: Dict[str,Any], path: Dict[str,Any]) -> float:
    weighted=[]
    for goal,priority in profile['goals'].items():
        if priority>0: weighted.append((path.get('goal_compatibility',{}).get(goal,40), priority))
    return weighted_average(weighted,60)

def apply_gates_and_adjustments(profile: Dict[str,Any], path: Dict[str,Any]) -> Tuple[bool,float,List[str],List[str]]:
    flags=set(profile['flags']); prefs=profile['preferences']; meta=profile['meta']
    eligible=True; adj=0.0; notes=[]; constraints=[]
    if 'REMOTE_REQUIREMENT' in flags and path['remote_compatibility'] < 40:
        eligible=False; constraints.append('This path conflicts with your requirement to work from home.')
    if 'NO_PHYSICAL_WORK' in flags and path['physical_intensity'] >= 70:
        eligible=False; constraints.append('This path conflicts with your preference to avoid physically demanding work.')
    if 'LIMITED_TRANSPORTATION' in flags and path['physical_intensity'] >= 70 and path['remote_compatibility'] < 20:
        adj -= 15; notes.append('-15 transportation constraint'); constraints.append('Limited transportation may make this local/mobile path harder to start.')
    if 'LIMITED_COMPUTER_ACCESS' in flags and path['capability_requirements'].get('TECH',0) >= 60:
        adj -= 15; notes.append('-15 limited computer access'); constraints.append('Reliable computer access is important for this path.')
    if 'LIMITED_INTERNET' in flags and path['remote_compatibility'] >= 80:
        adj -= 15; notes.append('-15 limited internet'); constraints.append('Reliable internet access is important for this path.')
    conflict=meta['INCOME_URGENCY'] - path['speed_to_validation']
    if conflict>0:
        pen=-5 if conflict<=20 else -10 if conflict<=40 else -20 if conflict<=60 else -30
        adj += pen; notes.append(f'{pen} income-urgency mismatch'); constraints.append('This path may take longer to validate than your current income timeline allows.')
    if path['prospecting_required'] >= 70:
        if prefs['PROSPECTING'] <=10:
            adj-=25; notes.append('-25 prospecting mismatch'); constraints.append('This path requires active prospecting, which you currently strongly prefer to avoid.')
        elif prefs['PROSPECTING'] <=30:
            adj-=15; notes.append('-15 prospecting mismatch'); constraints.append('This path depends on prospecting more than you currently prefer.')
    if path['work_style_targets'].get('VISIBILITY',0) >=65 and prefs['VISIBILITY'] <=20:
        adj-=10; notes.append('-10 visibility mismatch'); constraints.append('This path involves more public-facing work than you currently prefer.')
    return eligible,adj,notes,constraints

def score_band(score: float)->str:
    if score>=90:return 'Exceptional Fit'
    if score>=80:return 'Strong Fit'
    if score>=70:return 'Promising'
    if score>=60:return 'Possible'
    if score>=50:return 'Weak Fit'
    return 'Not Recommended'

def score_one(profile: Dict[str,Any], path: Dict[str,Any]) -> Optional[Dict[str,Any]]:
    eligible, adjustment, notes, constraints = apply_gates_and_adjustments(profile,path)
    if not eligible: return None
    cap, strengths, cap_gaps=capability_fit(profile,path)
    exp=experience_fit(profile,path); t=time_fit(profile,path); fin=financial_fit(profile,path)
    style=work_style_fit(profile,path); risk=risk_fit(profile,path); goal=goal_fit(profile,path); learn=learning_fit(profile,path)
    personal = cap*.20 + exp*.15 + t*.15 + fin*.15 + style*.15 + risk*.10 + goal*.10
    market=float(path['market_viability']); base=personal*.85 + market*.15; final=clamp(base+adjustment)
    constraints.extend(cap_gaps[:2])
    if fin<60: constraints.append('Startup capital is below the preferred level for this path.')
    if t<60: constraints.append('Available weekly time or learning runway is below the preferred level.')
    if risk<60: constraints.append('The risk profile is higher than your stated tolerance.')
    component_strengths=[]
    comps=[('capability fit',cap),('experience fit',exp),('time fit',t),('financial feasibility',fin),('work-style fit',style),('risk fit',risk),('goal alignment',goal)]
    for label,val in sorted(comps,key=lambda x:x[1],reverse=True)[:3]:
        if val>=75: component_strengths.append(f'Strong {label}.')
    component_strengths += strengths[:2]
    return dict(path=path,score=final,base_score=base,personal_fit=personal,market=market,capability=cap,experience=exp,time=t,financial=fin,style=style,risk=risk,goal=goal,learning=learn,adjustments=notes,strengths=component_strengths[:5],constraints=list(dict.fromkeys(constraints))[:5])

def diversify(scored: List[Dict[str,Any]], n=3) -> List[Dict[str,Any]]:
    if not scored:return []
    chosen=[scored[0]]; remaining=scored[1:]
    while len(chosen)<n and remaining:
        best=remaining[0]; families={x['path']['family'] for x in chosen}
        alternatives=[x for x in remaining if x['path']['family'] not in families and x['score'] >= best['score']-8]
        pick=alternatives[0] if alternatives else best
        chosen.append(pick); remaining=[x for x in remaining if x is not pick]
    return chosen

def to_result(x: Dict[str,Any]) -> PathResult:
    p=x['path']
    return PathResult(
        id=p['id'],name=p['name'],family=p['family'],score=round(x['score'],1),band=score_band(x['score']),
        personal_fit=round(x['personal_fit'],1),market_viability=round(x['market'],1),capability_fit=round(x['capability'],1),
        experience_fit=round(x['experience'],1),time_fit=round(x['time'],1),financial_fit=round(x['financial'],1),
        work_style_fit=round(x['style'],1),risk_fit=round(x['risk'],1),goal_fit=round(x['goal'],1),learning_fit=round(x['learning'],1),
        adjustments=x['adjustments'],strengths=x['strengths'],constraints=x['constraints'],first_move=p['first_move'],week_plan=p['week_plan']
    )

def evaluate(a: AssessmentInput) -> AssessmentResult:
    data=load_paths(); profile=build_profile(a); conflicts=detect_conflicts(a,profile); scored=[]
    for path in data['paths']:
        r=score_one(profile,path)
        if r and r['score']>=50: scored.append(r)
    scored.sort(key=lambda x:x['score'], reverse=True); top=diversify(scored,3)
    top_ids={x['path']['id'] for x in top}; long_term=None
    candidates=[x for x in scored if x['path']['id'] not in top_ids and x['base_score']>=78 and x['score'] <= (top[0]['score']-5 if top else 100)]
    if candidates:
        candidates.sort(key=lambda x:x['base_score']-x['score'], reverse=True)
        if candidates[0]['base_score']-candidates[0]['score'] >= 8: long_term=to_result(candidates[0])
    conf=confidence_score(a,conflicts); band='High Confidence' if conf>=80 else 'Moderate Confidence' if conf>=60 else 'Exploratory'
    return AssessmentResult(
        confidence_score=conf,confidence_band=band,conflicts=conflicts,
        trait_profile={k:round(v,1) for k,v in profile['capabilities'].items()},
        preference_profile={k:round(v,1) for k,v in profile['preferences'].items()},
        goal_profile={k:round(v,1) for k,v in profile['goals'].items()},
        top_paths=[to_result(x) for x in top],long_term_opportunity=long_term,market_version=data['market_version']
    )
