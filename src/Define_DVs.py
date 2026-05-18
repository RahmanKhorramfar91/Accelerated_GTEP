
# -*- coding: utf-8 -*-
"""
Bismillah
Created on Friday, 1 August 19:29 2025  

for now, the model is implemented for green frield only. 

@author: Rahman Khorramfar
"""
import pyoptinterface as poi;

def define_investment_decision_variables(Model, DV, data, Setting):

    # define decision variables for investment
    DV.gen_established = Model.add_variables(range(data.num_generators), range(data.num_nodes), lb=0, domain=poi.VariableDomain.Continuous);    
    DV.gen_operational = Model.add_variables(range(data.num_generators), range(data.num_nodes), lb=0, domain=poi.VariableDomain.Continuous);    
    DV.RPS_contribution_per_period= Model.add_variables(range(data.num_rep_periods), lb=0, domain=poi.VariableDomain.Continuous);
    DV.emissions_per_period = Model.add_variables(range(data.num_rep_periods), lb=0, domain=poi.VariableDomain.Continuous);
    DV.total_emissions = Model.add_variable(lb=0, domain=poi.VariableDomain.Continuous);
    for i in range(data.num_generators):
        if data.Generators[i].is_thermal and not Setting['relax_int_vars']:
            for n in range(data.num_nodes):DV.gen_established[i,n] = Model.add_variable(lb=0, domain=poi.VariableDomain.Integer);
                        
    DV.storage_capacity = Model.add_variables(range(data.num_storages), range(data.num_nodes), lb=0, domain=poi.VariableDomain.Continuous);
    DV.storage_level = Model.add_variables(range(data.num_storages), range(data.num_nodes), lb=0, domain=poi.VariableDomain.Continuous);  
    DV.line_established = Model.add_variables(range(data.num_lines), lb=0, domain=poi.VariableDomain.Continuous);   

    # cost components
    DV.total_investment_cost = Model.add_variable(lb=0, domain=poi.VariableDomain.Continuous);
    DV.gen_est_cost = Model.add_variable(lb=0, domain=poi.VariableDomain.Continuous);
    DV.line_est_cost = Model.add_variable(lb=0, domain=poi.VariableDomain.Continuous);
    DV.storage_est_cost = Model.add_variable(lb=0, domain=poi.VariableDomain.Continuous);
    DV.gen_FOM_cost = Model.add_variable(lb=0, domain=poi.VariableDomain.Continuous);
    DV.line_FOM_cost = Model.add_variable(lb=0, domain=poi.VariableDomain.Continuous);
    DV.storage_FOM_cost = Model.add_variable(lb=0, domain=poi.VariableDomain.Continuous);

    # used in BD
    DV.theta = Model.add_variables(range(data.num_rep_periods), lb=0, domain=poi.VariableDomain.Continuous);  
    DV.total_SP_cost = Model.add_variable(lb=0, domain=poi.VariableDomain.Continuous);


def define_operational_decision_variables(Model, DV, nT, data):

    # define decision variables for operation
    DV.generation = Model.add_variables(range(data.num_generators), range(data.num_nodes), range(nT), lb=0, domain=poi.VariableDomain.Continuous);
    DV.load_shedding = Model.add_variables(range(data.num_nodes), range(nT), lb=0, domain=poi.VariableDomain.Continuous);
    DV.storage_charge = Model.add_variables(range(data.num_storages), range(data.num_nodes), range(nT), lb=0, domain=poi.VariableDomain.Continuous);
    DV.storage_discharge = Model.add_variables(range(data.num_storages), range(data.num_nodes), range(nT), lb=0, domain=poi.VariableDomain.Continuous);
    DV.SOC = Model.add_variables(range(data.num_storages), range(data.num_nodes), range(nT), lb=0, domain=poi.VariableDomain.Continuous);
    DV.flow = Model.add_variables(range(data.num_lines), range(nT),  domain=poi.VariableDomain.Continuous);

    # cost components
    DV.operational_cost = Model.add_variable(lb=0, domain=poi.VariableDomain.Continuous);
    DV.VOM_cost = Model.add_variable(lb=0, domain=poi.VariableDomain.Continuous);
    DV.load_shedding_cost = Model.add_variable(lb=0, domain=poi.VariableDomain.Continuous);
    DV.gas_fuel_cost = Model.add_variable(lb=0, domain=poi.VariableDomain.Continuous);   
