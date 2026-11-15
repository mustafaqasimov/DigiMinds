"""Synthetic Baku-centered training area. NOT surveyed streets or official shelters."""
from .geo import distance


def seed_map():
    nodes = []
    for row in range(7):
        for col in range(9):
            nodes.append({'id':f'n{row}_{col}', 'lat':40.365+row*.0025, 'lng':49.828+col*.0035,
                          'x':80+col*102, 'y':660-row*85})
    lookup = {n['id']: n for n in nodes}
    edges = []
    for row in range(7):
        for col in range(9):
            for rr, cc in ((row+1,col),(row,col+1)):
                if rr>6 or cc>8: continue
                a,b=f'n{row}_{col}',f'n{rr}_{cc}'
                na,nb=lookup[a],lookup[b]
                edges.append({'id':f'{a}--{b}', 'a':a,'b':b,'blocked':False,
                              'meters':round(distance((na['lat'],na['lng']),(nb['lat'],nb['lng']))),
                              'name':f'Demo {"prospekt" if rr==row else "küçə"} {row+1 if rr==row else col+1}'})
    shelters=[
        {'id':'s1','name':'Mərkəz Parkı','node':'n3_4','capacity':400,'occupancy':248,'status':'open','kind':'park','area_m2':600},
        {'id':'s2','name':'Şimal Stadionu','node':'n6_5','capacity':1000,'occupancy':410,'status':'open','kind':'stadium','area_m2':1800},
        {'id':'s3','name':'Qərb Sığınacağı','node':'n4_1','capacity':200,'occupancy':156,'status':'open','kind':'shelter','area_m2':300},
        {'id':'s4','name':'Sahil Toplanış Sahəsi','node':'n1_7','capacity':600,'occupancy':180,'status':'open','kind':'park','area_m2':1000},
        {'id':'s5','name':'Ehtiyat Təhlükəsizlik Sahəsi','node':'n5_7','capacity':500,'occupancy':0,'status':'standby','kind':'park','area_m2':800},
        {'id':'s6','name':'Qərb Ehtiyat Sahəsi','node':'n1_1','capacity':300,'occupancy':0,'status':'standby','kind':'shelter','area_m2':400},
    ]
    teams=[
        {'id':'t1','name':'Atlas 01','skills':['fire','collapse'],'node':'n4_3','status':'available','incident_id':None},
        {'id':'t2','name':'Med 02','skills':['medical'],'node':'n2_5','status':'available','incident_id':None},
        {'id':'t3','name':'Delta 03','skills':['flood','collapse'],'node':'n5_6','status':'available','incident_id':None},
        {'id':'t4','name':'Rescue 04','skills':['fire','medical','flood','collapse'],'node':'n2_2','status':'available','incident_id':None},
    ]
    return {'nodes':nodes,'roads':edges,'shelters':shelters,'teams':teams,
            'zones':[{'id':'west','name':'Qərb zonası'},{'id':'east','name':'Şərq zonası'}],
            'dataset':'synthetic-training-baku-v1','bounds':[49.828,40.365,49.856,40.38],
            'notice':'Synthetic training map. Not official evacuation guidance.'}
