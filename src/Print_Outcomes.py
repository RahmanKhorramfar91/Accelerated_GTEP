"""
Bismillah
Created on Satuday, 2 August 18:44 2025  

@author: Rahman Khorramfar
"""
import numpy as np;
import pandas as pd;
import time, os, csv; 
import pyoptinterface as poi;
from pyoptinterface import gurobi;

def publish_extensive_form(DVi_vals, DVo_vals, data, Setting):

    rows = np.zeros((data.num_lines, data.num_generators+3));        
    for n in range(data.num_nodes):
        for g in range(data.num_generators):
            rows[n,g] = DVo_vals.gen_operational[g,n];
        rows[n, data.num_generators] = DVi_vals.storage_level[0,n];
        rows[n, data.num_generators+1] = DVi_vals.storage_capacity[0,n];
    for l in range(data.num_lines):
        rows[l, data.num_generators+2] = DVi_vals.line_established[l];

    cols = [str(data.Generators[g].Type) for g in range(data.num_generators)];
    cols.append('storage_level');
    cols.append('storage_capacity');
    cols.append('line');

    df = pd.DataFrame(rows, columns=cols);
    name =f"{os.getcwd()}/extended_outcomes/IS_{Setting['balancing_authority']}_nN={data.num_nodes}-nRep={Setting['num_rep_periods']}-RPS={Setting['RPS']}-CRM={Setting['CRM_reserve']}-Scen_list={Setting['in_sample_year']}_LP={Setting['relax_int_vars']}_CopperPlate={Setting['is_copper_plate_approx']}_SolMethod={Setting['solution_method']}.csv";
    df.to_csv(name, index=False);



    

        

def publish_summary(DVi_vals, DVo_vals, data, Setting, start_time, relative_gap, RAM_MB):

    res={};
    res['balancing authority'] = Setting['balancing_authority'];
    res['nNodes'] = data.num_nodes;
    res['in-sample year'] = Setting['in_sample_year'];    
    res['num_rep_periods'] = Setting['num_rep_periods'];
    res['hours_per_period'] = Setting['hours_per_period'];
    if Setting['solution_method']=='PHA':
        res['num_rep_periods'] = [Setting['num_rep_periods'], Setting['num_periods_per_scenario']];
    res['RPS'] = Setting['RPS'];
    res['Decarbonization target'] = Setting['Decarbonization_target'];
    res['CRM reserve'] = Setting['CRM_reserve'];
    res['is green field?'] = Setting['is_green_field'];
    res['is copper plate approx?'] = Setting['is_copper_plate_approx'];
    res['is UC active?'] = Setting['UC_active'];
    res['is integer vars relaxed?']= Setting['relax_int_vars'];
    res['is UC vars relaxed?']= Setting['relax_UC_vars'];

    res['relative gap'] = relative_gap;
    res['sol-method'] = Setting['solution_method'];
    res['RAM (MB)'] = RAM_MB;
    res['run time(s)'] = time.time()-start_time;

    res['total system cost'] = DVi_vals.total_investment_cost + DVo_vals.operational_cost;
    res['est gen cost'] = DVi_vals.gen_est_cost;
    res['est line cost'] = DVi_vals.line_est_cost;
    res['est storage cost'] = DVi_vals.storage_est_cost;
    res['VOM cost'] = DVo_vals.VOM_cost;
    res['shedding cost'] = DVo_vals.load_shedding_cost;
    res['gas fuel cost'] = DVo_vals.gas_fuel_cost;
    res['FOM gen cost'] = DVi_vals.gen_FOM_cost;
    res['FOM line cost'] = DVi_vals.line_FOM_cost;
    res['FOM storage cost'] = DVi_vals.storage_FOM_cost;
    res['CO2 emissions'] = sum(DVi_vals.emissions_per_period[d] for d in range(data.num_rep_periods));
    
    
    # calculate some values
    total_storage_level = sum( DVi_vals.storage_level[s,n] for s in range(data.num_storages) for n in range(data.num_nodes));
    total_storage_capacity = sum( DVi_vals.storage_capacity[s,n] for s in range(data.num_storages) for n in range(data.num_nodes));

    total_shed_load = sum(DVo_vals.load_shedding[n,t] for n in range(data.num_nodes) for t in range(data.num_rep_hours));
    num_established_lines = sum(1 for l in range(data.num_lines) if DVi_vals.line_established[l]>0)
    total_new_line_cap = sum(DVi_vals.line_established[l] for l in range(data.num_lines));

    res['total storage level'] = total_storage_level;
    res['total storage capacity'] = total_storage_capacity;
    res['total shed load']= total_shed_load;
    res['total established lines'] = num_established_lines;
    res['total new line capacity(MW)'] = total_new_line_cap;
    
    for g in range(data.num_generators):
        cap1=0;
        for n in range(data.num_nodes):
            cap1 += DVi_vals.gen_established[g,n];
        res[f'{data.Generators[g].Type}-cap'] = cap1;
    
    total_gen = 0;
    for g in range(data.num_generators):
        gen1=0;
        for n in range(data.num_nodes):
            for t in range(data.num_rep_hours):
                gen1 += DVo_vals.generation[g,n,t]*data.rep_hours_weights[t];
        res[f'{data.Generators[g].Type}-gen'] = gen1;
        total_gen += gen1;
    res['total generation'] = total_gen;   
    total_demand = sum(data.Nodes[n].demand[data.rep_hours[t]]*data.rep_hours_weights[t] for n in range(data.num_nodes) for t in range(data.num_rep_hours));
    res['total demand'] = total_demand;



    
    header = res.keys();
    row = res.values();

    with open(os.getcwd()+'/results_summary.csv', 'a', encoding='UTF8', newline='') as f:
        writer = csv.writer(f);
        if Setting['print_result_header']:
            writer.writerow(header);
        writer.writerow(row);
        f.close();







    
    
    

