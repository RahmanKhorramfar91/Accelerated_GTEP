# -*- coding: utf-8 -*-
"""
Bismillah
Created on Friday, 1 August 19:24 2025  

for now, the model is implemented for green frield only. 

@author: Rahman Khorramfar
"""
import numpy as np;
import pyoptinterface as poi;
from pyoptinterface import gurobi;
import os;
import pandas as pd;

def inv_const_num_operational_generators(Model, DV, data, Setting):      
        # number of operational generators at each node
        
    if Setting['is_green_field']:
        for g in range(data.num_generators):
            for n in range(data.num_nodes):     
                # if not data.Generators[g].is_thermal:  
                #     Model.add_linear_constraint(DV.gen_operational[g,n], poi.Eq, 0);
                Model.add_linear_constraint(DV.gen_operational[g,n]-DV.gen_established[g,n], poi.Eq, 0);
    else:
        pass; # only implemented for green field for now, can add brownfield later if needed

def inv_const_line_expansion_limits(Model, DV, data, Setting):
    # line expansion limits
    if Setting['expansion_allowed']:
        for l in range(data.num_lines):
            fn = data.Lines[l].from_node;
            tn = data.Lines[l].to_node;
            peak_loadf = np.max(data.Nodes[fn].demand[data.rep_hours]);
            peak_loadt = np.max(data.Nodes[tn].demand[data.rep_hours]);
            Model.add_linear_constraint(DV.line_established[l]-max(peak_loadf,peak_loadt)*Setting['line_limit_rate'], poi.Leq, 0);


def inv_const_land_availability_for_renewables(Model, DV, data):
    # land availability for renewables    
    for g in range(data.num_generators):
        if data.Generators[g].Type=='wind-new':
            for n in range(data.num_nodes):
                Model.add_linear_constraint(DV.gen_operational[g,n], poi.Leq, data.Nodes[n].area_wind* data.Generators[g].power2area_density);            
        if data.Generators[g].Type=='solar-UPV':
            for n in range(data.num_nodes):
                Model.add_linear_constraint(DV.gen_operational[g,n], poi.Leq, data.Nodes[n].area_solar* data.Generators[g].power2area_density);


def inv_const_CRM(Model, DV, data, Setting):
    # capacity reserve margin
    if Setting['CRM_reserve'] > 0:
        for t in range(data.num_rep_hours):
            Model.add_linear_constraint(
                poi.quicksum(data.Nodes[n].solar_cf[data.rep_hours[t]]*data.Generators[g].nameplate_capacity*DV.gen_operational[g,n] for g in range(data.num_generators) for n in range(data.num_nodes) if data.Generators[g].Type=='solar-UPV') +
                poi.quicksum(data.Nodes[n].wind_cf[data.rep_hours[t]]*data.Generators[g].nameplate_capacity*DV.gen_operational[g,n] for g in range(data.num_generators) for n in range(data.num_nodes) if data.Generators[g].Type=='wind-new') +
                poi.quicksum(data.Generators[g].nameplate_capacity*DV.gen_operational[g,n] for g in range(data.num_generators) for n in range(data.num_nodes) if data.Generators[g].is_thermal)-
                (1 + Setting['CRM_reserve'])* poi.quicksum(data.Nodes[n].demand[data.rep_hours[t]] for n in range(data.num_nodes)),
                poi.Geq, 0
            );

def inv_storage_duaration_range(Model, DV, data):
    # storage duration range    
    for s in range(data.num_storages):
        for n in range(data.num_nodes):
            Model.add_linear_constraint(DV.storage_level[s,n]-
            data.Storages[s].duration_range* DV.storage_capacity[s,n], poi.Eq, 0);
    

def inv_const_RPS(Model, DV, data, Setting):
    if Setting['RPS'] > 0:
        Model.add_linear_constraint(poi.quicksum(DV.RPS_contribution_per_period[d] for d in range(data.num_rep_periods)) - 
           Setting['RPS'] * poi.quicksum(data.rep_hours_weights[t]*(data.Nodes[n].demand[data.rep_hours[t]] - DV.load_shedding[n,t]) for n in range(data.num_nodes) for t in range(data.num_rep_hours)),
           poi.Geq, 0);

def inv_const_emissions_limit(Model, DV, data, Setting):
    if Setting['Decarbonization_target'] > 0:
        Model.add_linear_constraint(poi.quicksum(DV.emissions_per_period[d] for d in range(data.num_rep_periods)) - (1-Setting['Decarbonization_target'])* Setting['ISONE_power_emission_1990']*1000, poi.Leq, 0);



## operational constraints
# 
#     
def oper_const_production_limits(Model, DVi, DVo, Con, DVi_vals, sp_hours, data, Setting):         
    # production limits for each generator type at each node at each time period
    nT = len(sp_hours);
    Con.prod_limit =np.empty((data.num_generators, data.num_nodes, nT), dtype=object);


    if Setting['solution_method']=='extensive_form':  # all the same excep the rhs in RBD to capture duals
        for g in range(data.num_generators):
            for n in range(data.num_nodes):
                for t in range(nT):
                    if data.Generators[g].is_thermal:
                        Con.prod_limit[g,n,t] = Model.add_linear_constraint(DVo.generation[g,n,t]-data.Generators[g].nameplate_capacity*DVi.gen_operational[g,n], poi.Leq, 0);
                    elif data.Generators[g].Type=='solar-UPV':
                        Con.prod_limit[g,n,t] = Model.add_linear_constraint(DVo.generation[g,n,t]-data.Nodes[n].solar_cf[sp_hours[t]]*data.Generators[g].nameplate_capacity*DVi.gen_operational[g,n], poi.Leq, 0);
                    elif data.Generators[g].Type=='wind-new':
                        Con.prod_limit[g,n,t] = Model.add_linear_constraint(DVo.generation[g,n,t]-data.Nodes[n].wind_cf[sp_hours[t]]*data.Generators[g].nameplate_capacity*DVi.gen_operational[g,n], poi.Leq, 0);
    else:                
        for g in range(data.num_generators):
            for n in range(data.num_nodes):
                for t in range(nT):
                    if data.Generators[g].is_thermal:
                        Con.prod_limit[g,n,t] = Model.add_linear_constraint(DVo.generation[g,n,t], poi.Leq, data.Generators[g].nameplate_capacity*DVi_vals.gen_operational[g,n]);
                    elif data.Generators[g].Type=='solar-UPV':
                        Con.prod_limit[g,n,t] = Model.add_linear_constraint(DVo.generation[g,n,t], poi.Leq, data.Nodes[n].solar_cf[sp_hours[t]]*data.Generators[g].nameplate_capacity*DVi_vals.gen_operational[g,n]);
                    elif data.Generators[g].Type=='wind-new':
                        Con.prod_limit[g,n,t] = Model.add_linear_constraint(DVo.generation[g,n,t], poi.Leq, data.Nodes[n].wind_cf[sp_hours[t]]*data.Generators[g].nameplate_capacity*DVi_vals.gen_operational[g,n]);


def oper_const_ramping(Model, DVi, DVo, DVi_vals, Con, nT, data, Setting):  
    Con.ramp_limit_up = np.empty((data.num_generators, data.num_nodes, nT), dtype=object);
    Con.ramp_limit_down = np.empty((data.num_generators, data.num_nodes, nT), dtype=object);
    if Setting['solution_method']=='extensive_form':  
        for g in range(data.num_generators):
            if data.Generators[g].is_thermal:
                for n in range(data.num_nodes):
                    for t in range(1, nT):
                        Con.ramp_limit_up[g,n,t] = Model.add_linear_constraint(DVo.generation[g,n,t]-DVo.generation[g,n,t-1]-data.Generators[g].ramp_rate*data.Generators[g].nameplate_capacity*DVi.gen_operational[g,n], poi.Leq, 0);
                        Con.ramp_limit_down[g,n,t] = Model.add_linear_constraint(-DVo.generation[g,n,t]+DVo.generation[g,n,t-1]-data.Generators[g].ramp_rate*data.Generators[g].nameplate_capacity*DVi.gen_operational[g,n], poi.Leq, 0);
    else:
        for g in range(data.num_generators):
            if data.Generators[g].is_thermal:
                for n in range(data.num_nodes):
                    for t in range(1, nT):
                        Con.ramp_limit_up[g,n,t] = Model.add_linear_constraint(DVo.generation[g,n,t]-DVo.generation[g,n,t-1], poi.Leq, data.Generators[g].ramp_rate*data.Generators[g].nameplate_capacity*DVi_vals.gen_operational[g,n]);
                        Con.ramp_limit_down[g,n,t] = Model.add_linear_constraint(-DVo.generation[g,n,t]+DVo.generation[g,n,t-1], poi.Leq, data.Generators[g].ramp_rate*data.Generators[g].nameplate_capacity*DVi_vals.gen_operational[g,n]);


def oper_const_balance_equation(Model, DV, Con, sp_hours, data, Setting):
    nT = len(sp_hours);
    # balance equation for each node at each time period
    if Setting['is_copper_plate_approx']:
        Con.load_balance = np.empty((nT), dtype=object);
        for t in range(nT):
            rhs = 0;
            [rhs := rhs + data.Nodes[n].demand[sp_hours[t]] for n in range(data.num_nodes)];
            Con.load_balance[t] = Model.add_linear_constraint(
            poi.quicksum(DV.generation[g,n,t] for g in range(data.num_generators) for n in range(data.num_nodes)) +
            poi.quicksum(DV.storage_discharge[s,n,t] for s in range(data.num_storages) for n in range(data.num_nodes)) - 
            poi.quicksum(DV.storage_charge[s,n,t] for s in range(data.num_storages) for n in range(data.num_nodes)) +                                                                              
            poi.quicksum(DV.load_shedding[n,t]  for n in range(data.num_nodes)),
            poi.Eq, rhs 
        );
    else:   
        Con.load_balance = np.empty((data.num_nodes, nT), dtype=object); 
        for n in range(data.num_nodes):
            for t in range(nT):
                Con.load_balance[n,t] = Model.add_linear_constraint(
                    poi.quicksum(DV.generation[g,n,t] for g in range(data.num_generators)) -
                    poi.quicksum(data.Nodes[n].arc_signs[l]*DV.flow[data.Nodes[n].arcs[l],t] for l in range(len(data.Nodes[n].arcs))) +       
                    poi.quicksum(DV.storage_discharge[s,n,t] for s in range(data.num_storages)) - 
                    poi.quicksum(DV.storage_charge[s,n,t] for s in range(data.num_storages)) +                                                                              
                    DV.load_shedding[n,t],   
                    poi.Eq, data.Nodes[n].demand[sp_hours[t]]
                );


def oper_const_flow_limits(Model, DVi, DVo, DVi_vals, Con, nT, data, Setting):
    # flow limits for each line at each time period
    Con.flow_limit1 = np.empty((data.num_lines, nT), dtype=object);
    Con.flow_limit2 = np.empty((data.num_lines, nT), dtype=object);
    if Setting['solution_method']=='extensive_form':    
        if not Setting['is_copper_plate_approx']:
            for l in range(data.num_lines):
                for t in range(nT):
                    if data.Lines[l].is_existing:
                        Con.flow_limit1[l,t]= Model.add_linear_constraint(DVo.flow[l,t]-data.Lines[l].capacity-DVi.line_established[l], poi.Leq, 0);
                        Con.flow_limit2[l,t]= Model.add_linear_constraint(-DVo.flow[l,t]-data.Lines[l].capacity-DVi.line_established[l], poi.Leq, 0);
                    else:
                        Con.flow_limit1[l,t]= Model.add_linear_constraint(DVo.flow[l,t]-DVi.line_established[l], poi.Leq, 0);
                        Con.flow_limit2[l,t]= Model.add_linear_constraint(-DVo.flow[l,t]-DVi.line_established[l], poi.Leq, 0);
    else:
        if not Setting['is_copper_plate_approx']:
            for l in range(data.num_lines):
                for t in range(nT):
                    if data.Lines[l].is_existing:
                        Con.flow_limit1[l,t]= Model.add_linear_constraint(DVo.flow[l,t], poi.Leq, data.Lines[l].capacity-DVi_vals.line_established[l]);
                        Con.flow_limit2[l,t]= Model.add_linear_constraint(-DVo.flow[l,t], poi.Leq, data.Lines[l].capacity-DVi_vals.line_established[l]);
                    else:
                        Con.flow_limit1[l,t]= Model.add_linear_constraint(DVo.flow[l,t], poi.Leq, DVi_vals.line_established[l]);
                        Con.flow_limit2[l,t]= Model.add_linear_constraint(-DVo.flow[l,t], poi.Leq, DVi_vals.line_established[l]);


def oper_const_RPS(Model, DVi, DVo, data, Setting):
    # renewable portfolio standard
    if Setting['RPS'] > 0:
        # Model.add_linear_constraint(
        # poi.quicksum(data.rep_hours_weights[t]*DV.generation[g,n,t] for g in range(data.num_generators) for n in range(data.num_nodes) for t in range(data.num_rep_hours) if data.Generators[g].Type in ['solar-UPV', 'wind-new']) -
        # Setting['RPS'] * poi.quicksum(data.rep_hours_weights[t]*(data.Nodes[n].demand[data.rep_hours[t]] - DV.load_shedding[n,t]) for n in range(data.num_nodes) for t in range(data.num_rep_hours)),
        # poi.Geq, 0
        # );
        for d in range(data.num_rep_periods):
            Model.add_linear_constraint(DVi.RPS_contribution_per_period[d]-
            poi.quicksum(data.rep_hours_weights[t]*DVo.generation[g,n,t]
                         for g in range(data.num_generators) 
                         for n in range(data.num_nodes) 
                         for t in range(d*Setting['hours_per_period'], (d+1)*Setting['hours_per_period']) if data.Generators[g].Type in ['solar-UPV', 'wind-new']),
            poi.Eq, 0);

        
def oper_const_emissions_limit(Model, DVi, DVo, DVi_vals, Con, scen_set, hours_weights, data, Setting):
    # scen_set is the scenario set which is equal to the SP number in BD and to all rep-preiods in EF
    Con.emissions_limit = np.empty((len(scen_set)), dtype=object);
    if Setting['solution_method']=='extensive_form':
        if Setting['Decarbonization_target'] >0:
            for di, dv in enumerate(scen_set):
                Con.emissions_limit[dv] = Model.add_linear_constraint(
                    poi.quicksum(hours_weights[t]*DVo.generation[g,n,t]*data.Generators[g].heat_rate*data.Generators[g].emission_kg_per_MMBtu
                    for g in range(data.num_generators) 
                    for n in range(data.num_nodes) 
                    for t in range(dv*Setting['hours_per_period'], (dv+1)*Setting['hours_per_period']) if data.Generators[g].is_thermal)
                    -DVi.emissions_per_period[di], poi.Leq, 0); 
    else:
        if Setting['Decarbonization_target'] >0:
            for di, dv in enumerate(scen_set):
                Con.emissions_limit[di] = Model.add_linear_constraint(
                    poi.quicksum(hours_weights[t]*DVo.generation[g,n,t]*data.Generators[g].heat_rate*data.Generators[g].emission_kg_per_MMBtu
                    for g in range(data.num_generators) 
                    for n in range(data.num_nodes) 
                    for t in range(len(hours_weights)) if data.Generators[g].is_thermal),
                    poi.Leq, DVi_vals.emissions_per_period[dv]);    


def oper_const_storage(Model, DVi, DVo, DVi_vals, Con, nT, data, Setting):

    Con.storage_SOC_balance = np.empty((data.num_nodes), dtype=object);
    Con.storage_charge_limit = np.empty((data.num_nodes, nT), dtype=object);
    Con.storage_discharge_limit = np.empty((data.num_nodes, nT), dtype=object);
    Con.storage_SOC_limit = np.empty((data.num_nodes, nT), dtype=object);

    # storage constraints
    if Setting['solution_method']=='extensive_form':
        for s in range(data.num_storages):
            for n in range(data.num_nodes):
                for t in range(nT):
                    if t>0:
                        Model.add_linear_constraint(DVo.SOC[s,n,t]-(1-data.Storages[s].self_discharge)*DVo.SOC[s,n,t-1] -
                        data.Storages[s].charging_eff*DVo.storage_charge[s,n,t] +
                        DVo.storage_discharge[s,n,t]/data.Storages[s].discharging_eff,
                        poi.Eq, 0);
                    else:
                        Con.storage_SOC_balance[n] = Model.add_linear_constraint(DVo.SOC[s,n,t]-DVi.storage_level[s,n]/2, poi.Eq, 0);
                    
                    Con.storage_charge_limit[n,t] = Model.add_linear_constraint(DVo.storage_charge[s,n,t]-DVi.storage_capacity[s,n], poi.Leq, 0);
                    Con.storage_discharge_limit[n,t] = Model.add_linear_constraint(DVo.storage_discharge[s,n,t]-DVi.storage_capacity[s,n], poi.Leq, 0);
                    Con.storage_SOC_limit[n,t] = Model.add_linear_constraint(DVo.SOC[s,n,t]-DVi.storage_level[s,n], poi.Leq, 0);
    else:
        for s in range(data.num_storages):
            for n in range(data.num_nodes):
                for t in range(nT):
                    if t>0:
                        Model.add_linear_constraint(DVo.SOC[s,n,t]-(1-data.Storages[s].self_discharge)*DVo.SOC[s,n,t-1] -
                        data.Storages[s].charging_eff*DVo.storage_charge[s,n,t] +
                        DVo.storage_discharge[s,n,t]/data.Storages[s].discharging_eff,
                        poi.Eq, 0);
                    else:
                        Con.storage_SOC_balance[n] = Model.add_linear_constraint(DVo.SOC[s,n,t], poi.Eq, DVi_vals.storage_level[s,n]/2);
                    
                    Con.storage_charge_limit[n,t] = Model.add_linear_constraint(DVo.storage_charge[s,n,t], poi.Leq, DVi_vals.storage_capacity[s,n]);
                    Con.storage_discharge_limit[n,t] = Model.add_linear_constraint(DVo.storage_discharge[s,n,t], poi.Leq, DVi_vals.storage_capacity[s,n]);
                    Con.storage_SOC_limit[n,t] = Model.add_linear_constraint(DVo.SOC[s,n,t], poi.Leq, DVi_vals.storage_level[s,n]);

def set_inv_decision_from_in_sample(Model, DV, data, Setting):

    # to capture the establishment cost for generators
    inv_const_num_operational_generators(Model, DV, data, Setting);

    # read the csv file
    name =f"{os.getcwd()}/extended_outcomes/IS_{Setting['balancing_authority']}_nN={data.num_nodes}-nRep=2-RPS={Setting['RPS']}-CRM={Setting['CRM_reserve']}-Scen_list={Setting['in_sample_year']}_LP={Setting['relax_int_vars']}_CopperPlate={Setting['is_copper_plate_approx']}_SolMethod={Setting['solution_method']}.csv";
    df = pd.read_csv(name);
    
    for n in range(data.num_nodes):
        for g in range(data.num_generators):
            Model.add_linear_constraint(DV.gen_operational[g,n], poi.Eq, df.iloc[n,g]);
        
        Model.add_linear_constraint(DV.storage_level[0,n], poi.Eq, df.iloc[n, data.num_generators]);
        Model.add_linear_constraint(DV.storage_capacity[0,n], poi.Eq, df.iloc[n, data.num_generators+1]);
    
    for l in range(data.num_lines):
        Model.add_linear_constraint(DV.line_established[l], poi.Eq, df.iloc[l, data.num_generators+2]);
