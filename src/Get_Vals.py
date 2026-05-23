"""
Bismillah
Created on Satuday, 2 August 2:23 2025  

@author: Rahman Khorramfar
"""
import numpy as np;
import time; 
import pyoptinterface as poi;
from pyoptinterface import gurobi;




def get_investment_variable_values(Model, DV, DV_values, data):
    # retrieve the values of the decision variables after solving the model
    DV_values.gen_established = np.array([[max(0, Model.get_value(DV.gen_established[g, n])) for n in range(data.num_nodes)] for g in range(data.num_generators)]);
    DV_values.gen_operational = np.array([[max(0, Model.get_value(DV.gen_operational[g, n])) for n in range(data.num_nodes)] for g in range(data.num_generators)]);
    DV_values.storage_capacity = np.array([[max(0, Model.get_value(DV.storage_capacity[s, n])) for n in range(data.num_nodes)] for s in range(data.num_storages)]);
    DV_values.storage_level = np.array([[max(0, Model.get_value(DV.storage_level[s, n])) for n in range(data.num_nodes)] for s in range(data.num_storages)]);
    DV_values.line_established = np.array([max(0,Model.get_value(DV.line_established[l])) for l in range(data.num_lines)]);
    # DV_values.RPS_contribution_per_period = np.array([Model.get_value(DV.RPS_contribution_per_period[d]) for d in range(data.num_rep_periods)]);
    DV_values.emissions_per_period = np.array([max(0, Model.get_value(DV.emissions_per_period[d])) for d in range(data.num_rep_periods)]);

    # get the values of the cost components
    DV_values.total_investment_cost = Model.get_value(DV.total_investment_cost);
    DV_values.gen_est_cost = Model.get_value(DV.gen_est_cost);
    DV_values.line_est_cost = Model.get_value(DV.line_est_cost);
    DV_values.storage_est_cost = Model.get_value(DV.storage_est_cost);
    DV_values.gen_FOM_cost = Model.get_value(DV.gen_FOM_cost);
    DV_values.line_FOM_cost = Model.get_value(DV.line_FOM_cost);
    DV_values.storage_FOM_cost = Model.get_value(DV.storage_FOM_cost);

    # only used in BD
    DV_values.theta = np.array([max(0, Model.get_value(DV.theta[d])) for d in range(data.num_rep_periods)]);



def get_operational_variable_values(Model, DV, DV_values,nT, data):
   
    DV_values.generation = np.array([[[Model.get_value(DV.generation[g, n, t]) for t in range(nT)] for n in range(data.num_nodes)] for g in range(data.num_generators)]);
    DV_values.load_shedding = np.array([[Model.get_value(DV.load_shedding[n, t]) for t in range(nT)] for n in range(data.num_nodes)]);
    DV_values.storage_charge = np.array([[[Model.get_value(DV.storage_charge[s, n, t]) for t in range(nT)] for n in range(data.num_nodes)] for s in range(data.num_storages)]);
    DV_values.storage_discharge = np.array([[[Model.get_value(DV.storage_discharge[s, n, t]) for t in range(nT)] for n in range(data.num_nodes)] for s in range(data.num_storages)]);
    DV_values.SOC = np.array([[[Model.get_value(DV.SOC[s, n, t]) for t in range(nT)] for n in range(data.num_nodes)] for s in range(data.num_storages)]);
    DV_values.flow = np.array([[Model.get_value(DV.flow[l, t]) for t in range(nT)] for l in range(data.num_lines)]);

    
    # get the values of the cost components
    DV_values.operational_cost = Model.get_value(DV.operational_cost);
    DV_values.VOM_cost = Model.get_value(DV.VOM_cost); 
    DV_values.gas_fuel_cost = Model.get_value(DV.gas_fuel_cost); 
    DV_values.load_shedding_cost = Model.get_value(DV.load_shedding_cost);

def get_operational_constraint_dual_values(Model, Con, Duals, nT, data, Setting):
    # retrieve the values of the dual variables
    Duals.prod_limit =np.empty((data.num_generators, data.num_nodes, nT), dtype=object);

    Duals.ramp_limit_up = np.empty((data.num_generators,data.num_nodes, nT), dtype=object);
    Duals.ramp_limit_down = np.empty((data.num_generators, data.num_nodes, nT), dtype=object);

    for n in range(data.num_nodes):
        for t in range(nT):
            for g in range(data.num_generators):
                if data.Generators[g].is_thermal:
                    Duals.prod_limit[g,n,t] = Model.get_constraint_attribute(Con.prod_limit[g,n,t], poi.ConstraintAttribute.Dual);
                elif data.Generators[g].Type=='solar-UPV':
                    Duals.prod_limit[g,n,t] = Model.get_constraint_attribute(Con.prod_limit[g,n,t], poi.ConstraintAttribute.Dual);
                elif data.Generators[g].Type=='wind-new':
                    Duals.prod_limit[g,n,t] = Model.get_constraint_attribute(Con.prod_limit[g,n,t], poi.ConstraintAttribute.Dual);
                if t>0 and data.Generators[g].is_thermal:
                    Duals.ramp_limit_up[g,n,t] = Model.get_constraint_attribute(Con.ramp_limit_up[g,n,t], poi.ConstraintAttribute.Dual);
                    Duals.ramp_limit_down[g,n,t] = Model.get_constraint_attribute(Con.ramp_limit_down[g,n,t], poi.ConstraintAttribute.Dual);

    if Setting['is_copper_plate_approx']:
        Duals.load_balance = np.empty((nT), dtype=object);
        for t in range(nT):
            Duals.load_balance[t] = Model.get_constraint_attribute(Con.load_balance[t], poi.ConstraintAttribute.Dual);
    else:
        Duals.load_balance = np.empty((data.num_nodes, nT), dtype=object);
        for n in range(data.num_nodes):
            for t in range(nT):
                Duals.load_balance[n,t] = Model.get_constraint_attribute(Con.load_balance[n,t], poi.ConstraintAttribute.Dual);

    if not Setting['is_copper_plate_approx']:
        Duals.flow_limit1 = np.empty((data.num_lines, nT), dtype=object);
        Duals.flow_limit2 = np.empty((data.num_lines, nT), dtype=object);
        for l in range(data.num_lines):
            for t in range(nT):
                Duals.flow_limit1[l,t] = Model.get_constraint_attribute(Con.flow_limit1[l,t], poi.ConstraintAttribute.Dual);
                Duals.flow_limit2[l,t] = Model.get_constraint_attribute(Con.flow_limit2[l,t], poi.ConstraintAttribute.Dual);
                


    # storage constraints
    Duals.storage_SOC_balance = np.empty((data.num_nodes), dtype=object);
    Duals.storage_charge_limit = np.empty((data.num_nodes, nT), dtype=object);
    Duals.storage_discharge_limit = np.empty((data.num_nodes, nT), dtype=object);
    Duals.storage_SOC_limit = np.empty((data.num_nodes, nT), dtype=object);
    for s in range(data.num_storages):
        for n in range(data.num_nodes):
            for t in range(nT):
                if t==0:                                       
                    Duals.storage_SOC_balance[n] = Model.get_constraint_attribute(Con.storage_SOC_balance[n], poi.ConstraintAttribute.Dual);

                Duals.storage_charge_limit[n,t] = Model.get_constraint_attribute(Con.storage_charge_limit[n,t], poi.ConstraintAttribute.Dual);
                Duals.storage_discharge_limit[n,t] = Model.get_constraint_attribute(Con.storage_discharge_limit[n,t], poi.ConstraintAttribute.Dual);
                Duals.storage_SOC_limit[n,t] = Model.get_constraint_attribute(Con.storage_SOC_limit[n,t], poi.ConstraintAttribute.Dual);
    # emissions limit
    if Setting['Decarbonization_target'] > 0:
        Duals.emissions_limit = Model.get_constraint_attribute(Con.emissions_limit[0], poi.ConstraintAttribute.Dual);



def concat_SP_models_values(SP_DV_vals, DVo_vals, data, Setting):
    nT = len(data.rep_hours);
    DVo_vals.generation = np.zeros((data.num_generators, data.num_nodes, nT));
    DVo_vals.load_shedding = np.zeros((data.num_nodes, nT));
    DVo_vals.storage_charge = np.zeros((data.num_storages, data.num_nodes, nT));
    DVo_vals.storage_discharge = np.zeros((data.num_storages, data.num_nodes, nT));
    DVo_vals.SOC = np.zeros((data.num_storages, data.num_nodes, nT));
    DVo_vals.flow = np.zeros((data.num_lines, nT));
    DVo_vals.operational_cost = 0;
    DVo_vals.VOM_cost = 0;
    DVo_vals.gas_fuel_cost = 0;
    DVo_vals.load_shedding_cost = 0;

    
    for n in range(data.num_nodes):
        for d in range(data.num_rep_periods):
            # slice1 = np.arange(d*Setting['hours_per_period'], (d+1)*Setting['hours_per_period']);
            # sp_hours = data.rep_hours[slice1];
            # sp_hours_weights =data.rep_hours_weights[slice1];
            for t in range(Setting['hours_per_period']):
                for g in range(data.num_generators):
                    DVo_vals.generation[g,n,Setting['hours_per_period']*d+t] = SP_DV_vals[d].generation[g,n,t];
                DVo_vals.load_shedding[n,Setting['hours_per_period']*d+t] = SP_DV_vals[d].load_shedding[n,t];
                DVo_vals.storage_charge[0, n,Setting['hours_per_period']*d+t] = SP_DV_vals[d].storage_charge[0, n,t];
                DVo_vals.storage_discharge[0, n,Setting['hours_per_period']*d+t] = SP_DV_vals[d].storage_discharge[0, n,t];
                DVo_vals.SOC[0, n,Setting['hours_per_period']*d+t] = SP_DV_vals[d].SOC[0, n,t];

    for d in range(data.num_rep_periods):
        # slice1 = np.arange(d*Setting['hours_per_period'], (d+1)*Setting['hours_per_period']);
        # sp_hours = data.rep_hours[slice1];
        # sp_hours_weights =data.rep_hours_weights[slice1];
        for t in range(Setting['hours_per_period']): 
            DVo_vals.flow[:,d*Setting['hours_per_period']+t] = SP_DV_vals[d].flow[:,t];
        DVo_vals.operational_cost += SP_DV_vals[d].operational_cost;
        DVo_vals.VOM_cost += SP_DV_vals[d].VOM_cost;
        DVo_vals.gas_fuel_cost += SP_DV_vals[d].gas_fuel_cost;
        DVo_vals.load_shedding_cost += SP_DV_vals[d].load_shedding_cost;
    
    
          
                
