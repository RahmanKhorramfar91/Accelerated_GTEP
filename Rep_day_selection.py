# -*- coding: utf-8 -*-
"""
Created on Sun Jun 22 12:05:06 2025
Revised on May 6, 2026 to select rep. periods of different number of days (1, 3, 7)
@author: Rahman Khorramfar
"""

# from IPython import get_ipython;
# get_ipython().magic('reset -f') # to clear the namespace
# get_ipython().magic('clear');
import numpy as np
import pandas as pd;
# from sklearn_extra.cluster import KMedoids;
from pyclustering.cluster.kmedoids import kmedoids;
from scipy.spatial.distance import cdist;

def assign_to_fixed_medoids(X, medoids):
    distances = cdist(X, medoids, metric='euclidean')
    labels = np.argmin(distances, axis=1)
    return labels

ISO = ['ISONE']; # 'ISONE'
years = range(2005,2006); # 2001-2050
hours_per_rep_period = np.array([1,3,5,7])*24; 
num_rep_periods = np.array([2,5,10,20]); 

for iso in ISO:
    for yr in years:
        for dy in num_rep_periods:        
            for hpp in hours_per_rep_period:    
                # load the data
                if iso=='ISONE':  #based on 17 node, as the middle ground
                    data = pd.read_csv(f'ISONE_Demand_CF_17_node/{iso}_demand_{yr}.csv');
                # else:
                #     data = pd.read_csv(f'Demand_CFs_ISONE_ERCOT/demand_{iso}/demand_local_county_{yr}.csv');
                data = data.drop('Time', axis=1);
                data = data.iloc[:8760,:];
                last_day = 365-365%(hpp/24);
                data = data.iloc[:int(last_day*24),:];
                aggregated_df = data.groupby(data.index // hpp).sum();
                dg = np.array(aggregated_df.sum(axis=1));
                
                sorted_ind = np.argsort(dg);
                sorted_ind = sorted_ind[::-1];
                
                # cluster 
                n_init = dy;
                initial_medoids = sorted_ind[:n_init];
                if dy<5: # choose periods with the highest demand as the medoids
                    model = kmedoids(aggregated_df.to_numpy(), initial_medoids, itermax=1);
                else:
                    model = kmedoids(aggregated_df.to_numpy(), initial_medoids);
                model.process();
                
                # get clusters and medoids
                clusters = model.get_clusters();
                medoids = model.get_medoids();
                if dy*hpp>=8760: # covering the entire year, so all days are medoids
                    clusters = [[i] for i in  np.arange(365)];
                export = np.zeros((len(aggregated_df), 3));            
                for d in range(dy):
                    export[medoids[d],2] = 1;
                    for i in clusters[d]:
                        export[i, 1]=d;
                        
                export[:, 0] = np.arange(len(aggregated_df));                
                clus = pd.DataFrame(export, columns=['Day', 'Cluster', 'is_medoid?']);                
                clus.to_csv(f'Rep_periods/{iso}_{yr}_nPeriods={dy}_nHours={hpp}.csv', index=False);
                print(f'{iso} {yr} done for {dy} rep. periods of {hpp} hours each');


#%% calculate the annual demand


# from IPython import get_ipython;
# get_ipython().magic('reset -f') # to clear the namespace
# get_ipython().magic('clear');
# import numpy as np
# import pandas as pd;
# # from sklearn_extra.cluster import KMedoids;
# from pyclustering.cluster.kmedoids import kmedoids;
# from scipy.spatial.distance import cdist;

# ISO = ['ERCOT']; # 'ISONE'
# years = range(2040,2060); # 1996-2015
# num_rep_days = [4]; # 2-10 for small rep days, and 40-80 for the larger
# yd = np.zeros(20);
# peak = np.zeros(20);
# for iso in ISO:
#     for yi, yr in enumerate(years):
#         for dy in num_rep_days:            
#             # load the data
#             if iso=='ISONE':
#                 data = pd.read_csv(f'Demand_CFs_ISONE_ERCOT/demand_{iso}/demand_local_county_hourly_{yr}.csv');
#             else:
#                 data = pd.read_csv(f'Demand_CFs_ISONE_ERCOT/demand_{iso}/demand_local_county_{yr}.csv');
#             data = data.drop('Time_UTC', axis=1);
#             data = data.iloc[:8760,:];
#             aggregated_df = data.groupby(data.index // 24).sum();
#             dg = np.array(aggregated_df.sum(axis=1));
#             peak[yi] = data.max().max();
#             sorted_ind = np.argsort(dg);
#             sorted_ind = sorted_ind[::-1];
#             yd[yi]= np.sum(dg);
          


