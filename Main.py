"""
Bismillah
originally created on Wed 30 July 18:56:12 2025, for the NE paper with Liying
Modified here for the computation work using GNN

The current model is deterministic, ideally running for the entire year
 
@author: Rahman Khorramfar
"""

import numpy as np
import time;
from Setting import Setting;
import sys; 
from src.Data_Loader import Data;
from src.Model_Class import Power_System_Model;
# from src.BD_Class import BD;
from src.Benders import BD;
# from src.RBD import RBD;
import psutil, os;  # for memory usage

#%% Set Default Setting for the Porblem 

if len(sys.argv)>1:
    print(str(sys.argv));
    Setting['evaluation_type'] = sys.argv[1];
    Setting['in_sample_year'] = int(sys.argv[2]);
    Setting['num_rep_periods'] = int(sys.argv[4]);
    Setting['RPS'] = float(sys.argv[5]);
    Setting['solver_gap'] = float(sys.argv[6]);
    Setting['wall_clock_time_lim'] = int(sys.argv[7]); # hour
    Setting['solver_thread_num'] = int(sys.argv[8]);
    Setting['CRM_reserve'] = float(sys.argv[9]);
    
start_time = time.time();
Setting['balancing_authority'] = 'ISONE';
Setting['network_size'] = 6;
Setting['in_sample_year'] = 2005;
Setting['num_rep_periods'] = 2;
Setting['hours_per_period'] = 7 * 24;
Setting['RPS'] = 0.0;
Setting['Decarbonization_target'] = 0.8;
# Setting['solution_method'] = 'extensive_form';
Setting['solution_method'] = 'RBD'; # Regularized Benders

data = Data(Setting);

if Setting['solution_method']=='extensive_form':
    power_model = Power_System_Model(data, Setting);
    power_model.build_model();
    power_model.solve_EF_model();
    power_model.get_DV_values();
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info();
    RAM_MB = memory_info.rss / (1024 * 1024);
    power_model.print_results(start_time, RAM_MB);
if Setting['solution_method'] == 'benders_multicut':
    power_model= BD();
    power_model.Benders_run(data, Setting);
if Setting['solution_method'] == 'RBD':
    Benders_model = BD(data, Setting);
    Benders_model.run_Benders();

process = psutil.Process(os.getpid());
memory_info = process.memory_info();
print(f"Memory Usage (RSS): {memory_info.rss / (1024 * 1024):.2f} MB");
# print(data.num_generators, data.num_nodes, data.num_lines, data.rep_periods, data.num_storages, );
print("End of Main.py");

