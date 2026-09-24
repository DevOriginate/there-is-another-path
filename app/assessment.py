from __future__ import annotations

from typing import Dict, Any, List
from .models import AssessmentInput

CAPS = ['TECH','SALES','CREATIVE','ANALYTICAL','TEACHING','LEADERSHIP','ORGANIZATION','HANDS_ON']
PREFS = ['REMOTE','STABILITY','INDEPENDENCE','VISIBILITY','SALES_COMFORT','TECH_COMFORT','PROSPECTING']
GOALS = ['EXTRA_INCOME','CAREER_CHANGE','ENTREPRENEURSHIP','SELF_EMPLOYMENT','REMOTE_WORK','STABILITY_GOAL','LONG_TERM_WEALTH','PURPOSE','SKILL_BUILDING','EXPERIENCE_MONETIZATION']

def clamp(v, lo=0, hi=100):
    return max(lo, min(hi, v))

def build_profile(a: AssessmentInput) -> Dict[str, Any]:
    c = {k: 50.0 for k in CAPS}
    p = {k: 50.0 for k in PREFS}
    g = {k: 0.0 for k in GOALS}
    meta: Dict[str, Any] = {}
    tags: set[str] = set()
    flags: set[str] = set()

    if a.current_situation == 'full_time_employee': p['STABILITY'] += 15
    elif a.current_situation == 'part_time_employee': p['STABILITY'] += 5; meta['AVAILABLE_FLEXIBILITY'] = 60
    elif a.current_situation == 'self_employed': p['INDEPENDENCE'] += 20; p['SALES_COMFORT'] += 5; meta['RISK_BONUS'] = 5
    elif a.current_situation == 'freelancer': p['INDEPENDENCE'] += 20; p['SALES_COMFORT'] += 10; p['PROSPECTING'] += 10
    elif a.current_situation == 'business_owner': g['ENTREPRENEURSHIP'] += 25; c['LEADERSHIP'] += 10; c['SALES'] += 5; meta['RISK_BONUS'] = 10
    elif a.current_situation == 'student': g['SKILL_BUILDING'] += 20; meta['EXPERIENCE_LEVERAGE_PENALTY'] = 15
    elif a.current_situation == 'unemployed': meta['INCOME_URGENCY_BONUS'] = 20; p['STABILITY'] += 10
    elif a.current_situation == 'retired': g['EXPERIENCE_MONETIZATION'] += 20
    elif a.current_situation == 'between_careers': g['CAREER_CHANGE'] += 25

    direction = {'clear':100,'idea_unsure':75,'several_ideas':50,'stuck':30,'want_different':20,'starting_over':15}
    meta['DIRECTION_CLARITY'] = direction[a.professional_direction]
    if a.professional_direction == 'starting_over': g['CAREER_CHANGE'] += 15

    goal_map = {
        'extra_income':['EXTRA_INCOME'], 'new_career':['CAREER_CHANGE'], 'start_business':['ENTREPRENEURSHIP'],
        'work_for_myself':['SELF_EMPLOYMENT'], 'remote_work':['REMOTE_WORK'], 'leave_job_eventually':['CAREER_CHANGE'],
        'meaningful_work':['PURPOSE'], 'use_experience_differently':['EXPERIENCE_MONETIZATION'],
        'learn_valuable_skill':['SKILL_BUILDING']
    }
    for i, obj in enumerate(a.primary_objectives):
        val = 60 if i == 0 else 40
        for target in goal_map.get(obj, []): g[target] += val
        if obj == 'work_for_myself': p['INDEPENDENCE'] += 15
        if obj == 'remote_work': p['REMOTE'] += 20
        if obj == 'leave_job_eventually': p['INDEPENDENCE'] += 10
        if obj == 'rebuild_after_setback': flags.add('REBUILD_MODE')

    impact_level = {'250_month':1,'500_month':2,'1000_month':3,'2500_month':4,'replace_income':5,'build_business_long_term':5,'money_not_primary':0}
    meta['INCOME_TARGET_LEVEL'] = impact_level[a.financial_impact]
    if a.financial_impact == 'build_business_long_term':
        g['ENTREPRENEURSHIP'] += 20; g['LONG_TERM_WEALTH'] += 20
    if a.financial_impact == 'money_not_primary': g['PURPOSE'] += 15

    meta['CAPITAL_LEVEL'] = {'0':0,'up_to_100':1,'100_500':2,'500_1500':3,'1500_5000':4,'5000_plus':5}[a.available_capital]
    urgency = {'asap':100,'30_days':90,'3_months':70,'6_months':50,'1_year':25,'patient':5}[a.income_urgency]
    meta['INCOME_URGENCY'] = clamp(urgency + meta.get('INCOME_URGENCY_BONUS',0))
    risk = {'almost_none':10,'low':30,'moderate':55,'high':80,'significant':100}[a.risk_tolerance]
    meta['RISK_TOLERANCE'] = clamp(risk + meta.get('RISK_BONUS',0))
    if a.risk_tolerance == 'almost_none': p['STABILITY'] += 20
    elif a.risk_tolerance == 'low': p['STABILITY'] += 10
    elif a.risk_tolerance == 'high': p['INDEPENDENCE'] += 5
    elif a.risk_tolerance == 'significant': g['ENTREPRENEURSHIP'] += 10

    meta['TIME_WEEK'] = {'lt3':2,'3_5':4,'5_10':7,'10_20':15,'20_40':30,'40_plus':45}[a.weekly_time]
    meta['SCHEDULE_TYPE'] = a.schedule
    meta['SCHEDULE_FLEXIBILITY'] = 100 if a.schedule == 'flexible' else 30 if a.schedule == 'changes' else 60
    meta['LEARNING_HORIZON'] = {'immediate':10,'few_weeks':30,'1_3_months':50,'3_6_months':70,'6_12_months':85,'extensive':100}[a.learning_horizon]
    meta['EXPERIENCE_YEARS'] = {'none':0,'lt2':1,'2_5':4,'5_10':8,'10_20':15,'20_30':25,'30_plus':35}[a.experience_years]

    exp_trait_mods = {
        'sales':{'SALES':12}, 'customer_service':{'SALES':5,'TEACHING':3}, 'management':{'LEADERSHIP':15,'ORGANIZATION':10},
        'finance':{'ANALYTICAL':12,'ORGANIZATION':8}, 'technology':{'TECH':15,'ANALYTICAL':5},
        'construction':{'HANDS_ON':15,'ANALYTICAL':5}, 'education':{'TEACHING':15},
        'logistics':{'ORGANIZATION':15,'ANALYTICAL':8}, 'manufacturing':{'ORGANIZATION':8,'HANDS_ON':8},
        'marketing':{'CREATIVE':8,'SALES':8,'ANALYTICAL':5}, 'administration':{'ORGANIZATION':15},
        'creative':{'CREATIVE':15}, 'entrepreneurship':{'LEADERSHIP':10,'SALES':8}
    }
    for area in a.experience_areas:
        if area not in {'none','other'}: tags.add(f'EXP_{area.upper()}')
        for trait, delta in exp_trait_mods.get(area, {}).items(): c[trait] += delta
        if area == 'entrepreneurship': p['INDEPENDENCE'] += 10

    nat_mods = {
        'talking':{'SALES':12,'TEACHING':4}, 'selling':{'SALES':18}, 'teaching':{'TEACHING':18},
        'writing':{'CREATIVE':12}, 'designing':{'CREATIVE':18}, 'building':{'HANDS_ON':12,'ANALYTICAL':5},
        'repairing':{'HANDS_ON':18,'ANALYTICAL':5}, 'numbers':{'ANALYTICAL':15}, 'technology':{'TECH':18},
        'organizing':{'ORGANIZATION':18}, 'leading':{'LEADERSHIP':18}, 'researching':{'ANALYTICAL':12},
        'problem_solving':{'ANALYTICAL':18}, 'creating_content':{'CREATIVE':15}, 'negotiating':{'SALES':15},
        'working_with_hands':{'HANDS_ON':18}, 'helping_people':{'TEACHING':8}, 'analyzing_information':{'ANALYTICAL':18}
    }
    for act in a.natural_activities:
        for trait, delta in nat_mods[act].items(): c[trait] += delta

    for choice in a.forced_choices.values():
        if choice == 'customers': c['SALES'] += 12
        elif choice == 'computer': c['TECH'] += 6; p['INDEPENDENCE'] += 5
        elif choice == 'build': c['HANDS_ON'] += 8; c['TECH'] += 5
        elif choice == 'sell': c['SALES'] += 12
        elif choice == 'technical': c['TECH'] += 10; c['ANALYTICAL'] += 8
        elif choice == 'people': c['TEACHING'] += 8; c['SALES'] += 5
        elif choice == 'create': c['CREATIVE'] += 12
        elif choice == 'improve': c['ANALYTICAL'] += 8; c['ORGANIZATION'] += 8

    p['REMOTE'] = {'fully_remote':100,'mostly_remote':80,'hybrid':55,'in_person':20,'outdoors':0,'no_preference':50}[a.work_location]
    if a.work_location == 'outdoors': c['HANDS_ON'] += 8

    ep = a.economic_model_preference
    if ep == 'stable_paycheck': p['STABILITY'] = 100; p['INDEPENDENCE'] -= 10
    elif ep == 'freelancing': p['INDEPENDENCE'] += 20; p['STABILITY'] = 35
    elif ep == 'small_business': g['ENTREPRENEURSHIP'] += 25; p['INDEPENDENCE'] += 20
    elif ep == 'scalable_business': g['ENTREPRENEURSHIP'] += 30; g['LONG_TERM_WEALTH'] += 20; meta['RISK_TOLERANCE'] = clamp(meta['RISK_TOLERANCE']+5)
    elif ep == 'selling_products': g['ENTREPRENEURSHIP'] += 20
    elif ep == 'selling_services': c['SALES'] += 8; p['INDEPENDENCE'] += 15
    elif ep == 'consulting': g['EXPERIENCE_MONETIZATION'] += 20; c['TEACHING'] += 5; c['SALES'] += 5

    sc_map = {1:10,2:30,3:50,4:75,5:100}; trait_mod = {1:-15,2:-8,3:0,4:8,5:15}
    p['SALES_COMFORT'] = sc_map[a.sales_comfort]; c['SALES'] += trait_mod[a.sales_comfort]
    p['TECH_COMFORT'] = sc_map[a.tech_comfort]; c['TECH'] += trait_mod[a.tech_comfort]
    p['VISIBILITY'] = sc_map[a.visibility_comfort]

    constraints = set(a.constraints)
    if 'need_work_from_home' in constraints: flags.add('REMOTE_REQUIREMENT')
    if 'avoid_physical_work' in constraints: flags.add('NO_PHYSICAL_WORK')
    if 'limited_transportation' in constraints: flags.add('LIMITED_TRANSPORTATION')
    if 'limited_computer_access' in constraints: flags.add('LIMITED_COMPUTER_ACCESS')
    if 'limited_internet' in constraints: flags.add('LIMITED_INTERNET')
    if 'full_time_job' in constraints: flags.add('FULL_TIME_JOB')
    if 'dependents' in constraints: flags.add('DEPENDENTS')

    p['PROSPECTING'] = {'yes':100,'maybe':65,'online_only':60,'prefer_not':30,'absolutely_not':5}[a.prospecting]
    if a.prospecting == 'online_only': flags.add('ONLINE_ONLY_PROSPECTING')

    outcome = a.five_year_outcome
    if outcome == 'better_paying_career': g['CAREER_CHANGE'] += 35; p['STABILITY'] += 10
    elif outcome == 'work_independently': g['SELF_EMPLOYMENT'] += 35; p['INDEPENDENCE'] += 15
    elif outcome == 'small_business': g['ENTREPRENEURSHIP'] += 40
    elif outcome == 'scalable_company': g['ENTREPRENEURSHIP'] += 50; g['LONG_TERM_WEALTH'] += 20
    elif outcome == 'remote_anywhere': g['REMOTE_WORK'] += 40; p['REMOTE'] += 15
    elif outcome == 'financial_stability': g['STABILITY_GOAL'] += 30; p['STABILITY'] += 10
    elif outcome == 'more_free_time': meta['LIFESTYLE_FLEXIBILITY'] = 100
    elif outcome == 'meaningful_work': g['PURPOSE'] += 40
    elif outcome == 'semi_retirement': g['EXPERIENCE_MONETIZATION'] += 20; meta['LIFESTYLE_FLEXIBILITY'] = 70

    meta['PRIMARY_FEAR'] = a.primary_fear
    meta['HELP_TEXT'] = a.help_text.strip()
    meta['TWELVE_MONTH_CHANGE'] = a.twelve_month_change.strip()
    meta['AGE_BAND'] = a.age_band
    meta['CURRENT_SITUATION'] = a.current_situation

    return {
        'capabilities': {k:clamp(v) for k,v in c.items()},
        'preferences': {k:clamp(v) for k,v in p.items()},
        'goals': {k:clamp(v) for k,v in g.items()},
        'meta': meta, 'experience_tags': sorted(tags), 'flags': sorted(flags)
    }

def detect_conflicts(a: AssessmentInput, profile: Dict[str,Any]) -> List[str]:
    conflicts = []
    if a.economic_model_preference in {'small_business','scalable_business','selling_services','consulting'} and a.sales_comfort <= 2 and a.prospecting in {'prefer_not','absolutely_not'}:
        conflicts.append('You show interest in an independent business model but currently have low comfort with selling and prospecting.')
    if a.income_urgency in {'asap','30_days'} and a.learning_horizon in {'6_12_months','extensive'}:
        conflicts.append('You need income quickly but are also open to a long training runway; the engine will separate immediate and long-term paths.')
    if a.work_location == 'fully_remote' and 'avoid_physical_work' not in a.constraints and a.economic_model_preference == 'small_business':
        conflicts.append('You prefer fully remote work while also showing interest in small business; remote-compatible businesses will be prioritized.')
    if a.economic_model_preference == 'stable_paycheck' and a.five_year_outcome == 'scalable_company':
        conflicts.append('You value a stable paycheck today but ultimately want a scalable company; recommendations may use a staged transition.')
    return conflicts

def confidence_score(a: AssessmentInput, conflicts: List[str]) -> int:
    score = 88
    if a.help_text.strip(): score += 4
    if a.twelve_month_change.strip(): score += 4
    if len(a.natural_activities) >= 3: score += 2
    score -= min(15, 5*len(conflicts))
    return int(clamp(score))
