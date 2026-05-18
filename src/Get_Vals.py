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
    DV_values.gen_established = np.array([[Model.get_value(DV.gen_established[g, n]) for n in range(data.num_nodes)] for g in range(data.num_generators)]);
    DV_values.gen_operational = np.array([[Model.get_value(DV.gen_operational[g, n]) for n in range(data.num_nodes)] for g in range(data.num_generators)]);
    DV_values.storage_capacity = np.array([[Model.get_value(DV.storage_capacity[s, n]) for n in range(data.num_nodes)] for s in range(data.num_storages)]);
    DV_values.storage_level = np.array([[Model.get_value(DV.storage_level[s, n]) for n in range(data.num_nodes)] for s in range(data.num_storages)]);
    DV_values.line_established = np.array([Model.get_value(DV.line_established[l]) for l in range(data.num_lines)]);
    # DV_values.RPS_contribution_per_period = np.array([Model.get_value(DV.RPS_contribution_per_period[d]) for d in range(data.num_rep_periods)]);
    DV_values.emissions_per_period = np.array([Model.get_value(DV.emissions_per_period[d]) for d in range(data.num_rep_periods)]);

    # get the values of the cost components
    DV_values.total_investment_cost = Model.get_value(DV.total_investment_cost);
    DV_values.gen_est_cost = Model.get_value(DV.gen_est_cost);
    DV_values.line_est_cost = Model.get_value(DV.line_est_cost);
    DV_values.storage_est_cost = Model.get_value(DV.storage_est_cost);
    DV_values.gen_FOM_cost = Model.get_value(DV.gen_FOM_cost);
    DV_values.line_FOM_cost = Model.get_value(DV.line_FOM_cost);
    DV_values.storage_FOM_cost = Model.get_value(DV.storage_FOM_cost);


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

def get_dual_values(Model, Con, Duals, data, Setting):
   
    if Setting['is_copper_plate_approx']:
        Duals.load_balance = np.empty((data.num_rep_hours), dtype=object);
        for t in range(data.num_rep_hours):
            Duals.load_balance[t] = Model.get_constraint_attribute(Con.load_balance[t], poi.ConstraintAttribute.Dual);
    else:
        Duals.load_balance = np.empty((data.num_nodes, data.num_rep_hours), dtype=object);
        for n in range(data.num_nodes):
            for t in range(data.num_rep_hours):
                Duals.load_balance[n,t] = Model.get_constraint_attribute(Con.load_balance[n,t], poi.ConstraintAttribute.Dual);

    if not Setting['is_copper_plate_approx']:
        Duals.flow_limit1 = np.empty((data.num_lines, data.num_rep_hours), dtype=object);
        Duals.flow_limit2 = np.empty((data.num_lines, data.num_rep_hours), dtype=object);
        for l in range(data.num_lines):
            for t in range(data.num_rep_hours):
                Duals.flow_limit1[l,t] = Model.get_constraint_attribute(Con.flow_limit1[l,t], poi.ConstraintAttribute.Dual);
                Duals.flow_limit2[l,t] = Model.get_constraint_attribute(Con.flow_limit2[l,t], poi.ConstraintAttribute.Dual);
                



