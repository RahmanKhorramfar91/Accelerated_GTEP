# -*- coding: utf-8 -*-
"""
Bismillah
Created on Friday, 1 August 19:33 2025  

for now, the model is implemented for green frield only. 

@author: Rahman Khorramfar
"""
import numpy as np;
import time; 
import pyoptinterface as poi;
from pyoptinterface import gurobi;

def define_extensive_form_objective(Model, DVi, DVo, data, Setting):

    # investment cost expressions
    define_investment_cost_expression(Model, DVi, data, Setting);

    # operational cost expressions
    define_operational_cost_expression(Model, DVo, data.rep_hours_weights, data, Setting);

    # set the objective function                                 
    Model.set_objective(DVi.total_investment_cost + DVo.operational_cost, poi.ObjectiveSense.Minimize);



def define_investment_cost_expression(Model, DV, data, Setting):

    # generation establishment cost 
    Model.add_linear_constraint(DV.gen_est_cost-poi.quicksum(data.Generators[g].annualized_capex_per_unit * DV.gen_established[g, n] for g in range(data.num_generators) for n in range(data.num_nodes)), poi.Eq, 0);
    # generation fixed operation and maintenance cost
    Model.add_linear_constraint(DV.gen_FOM_cost-poi.quicksum(data.Generators[g].FOM_per_MW * DV.gen_operational[g, n] for g in range(data.num_generators) for n in range(data.num_nodes)), poi.Eq, 0);

    # line establishment cost
    Model.add_linear_constraint(DV.line_est_cost- poi.quicksum(data.Lines[l].annualized_capex * DV.line_established[l] for l in range(data.num_lines)), poi.Eq, 0);

    # line fixed operation and maintenance cost
    Model.add_linear_constraint(DV.line_FOM_cost-poi.quicksum(data.Lines[l].FOM*data.Lines[l].length * DV.line_established[l] for l in range(data.num_lines)), poi.Eq, 0);

    # storage establishment cost
    Model.add_linear_constraint(DV.storage_est_cost-poi.quicksum(data.Storages[s].annualized_power_capex_per_MW * DV.storage_capacity[s,n] + data.Storages[s].annualized_energy_capex_per_MW * DV.storage_level[s,n] for s in range(data.num_storages) for n in range(data.num_nodes)), poi.Eq, 0);

    # storage fixed operation and maintenance cost
    Model.add_linear_constraint(DV.storage_FOM_cost-poi.quicksum(data.Storages[s].FOM_power * DV.storage_capacity[s,n]+ data.Storages[s].FOM_energy*DV.storage_level[s,n] for s in range(data.num_storages) for n in range(data.num_nodes)), poi.Eq, 0);
    
    # total investment cost
    Model.add_linear_constraint(DV.total_investment_cost-
                                DV.gen_est_cost- 
                                DV.gen_FOM_cost-
                                DV.line_est_cost - 
                                DV.line_FOM_cost - 
                                DV.storage_est_cost- 
                                DV.storage_FOM_cost, 
                                poi.Eq, 0);


def define_operational_cost_expression(Model, DV, hours_weights, data, Setting):
    nT = len(hours_weights);
    # generation variable operation and maintenance cost
    Model.add_linear_constraint(DV.VOM_cost-poi.quicksum(hours_weights[t]* data.Generators[g].VOM_per_MWh * DV.generation[g, n, t] for g in range(data.num_generators) for n in range(data.num_nodes) for t in range(nT)), poi.Eq, 0);

    # load shedding cost
    Model.add_linear_constraint(DV.load_shedding_cost-poi.quicksum(hours_weights[t]*DV.load_shedding[n, t] * Setting['load_shedding_penalty'] for n in range(data.num_nodes) for t in range(nT)), poi.Eq, 0);

    # gas fuel cost
    Model.add_linear_constraint(DV.gas_fuel_cost-poi.quicksum(hours_weights[t]*data.Generators[g].heat_rate* DV.generation[g, n, t] * Setting['NG_price'] for g in range(data.num_generators) for n in range(data.num_nodes) for t in range(nT) if data.Generators[g].is_thermal), poi.Eq, 0); 

    # total operational cost
    Model.add_linear_constraint(DV.operational_cost-
                                DV.VOM_cost - 
                                DV.load_shedding_cost - 
                                DV.gas_fuel_cost, 
                                poi.Eq, 0);

def define_MP_objective(Model, DV, data, Setting):

    # investment cost expressions
    define_investment_cost_expression(Model, DV, data, Setting);

    # set the objective function                                 
    set_MP_objective(Model, DV, data);

def set_MP_objective(Model, DV, data):
    # reset the objective without re-adding the investment cost constraints
    Model.set_objective(DV.total_investment_cost+poi.quicksum(DV.theta[s] for s in range(data.num_rep_periods)), poi.ObjectiveSense.Minimize);
