# -*- coding: utf-8 -*-
"""
Bismillah
Created on Tuesday, 5 August 10:08 2025  
Revised on Sunday, May 10, 2026

implementation of the multi cut Benders in which each period is treated as a subproblem

@author: Rahman Khorramfar
"""
import numpy as np;
import pyoptinterface as poi;
import src.Constraints as Constraints;

def build_MP_model(Model, DV,  data, Setting):

    '''
    build the master problem model including all the decision variables and constraints pertained to the first stage variables
    The optimality and feasibility custs will be added to the created model later in another function
    Arg: data, Setting

    Return: Model
    '''
    define_MP_decision_variables(Model, DV, data, Setting);
    
    MP_cost = define_MP_objective(Model, DV, data, Setting);
    # set the objective function                                 
    Model.set_objective(MP_cost, poi.ObjectiveSense.Minimize);
    MP_constraints(Model, DV, data, Setting);
    
    return Model, DV.MP_cost;
    

class MP_Decision_Variables:
    def __init__(self):
        # set of investment decision variables
        self.gen_established = [];      # established unt/capacity per generator (at each node)
        self.gen_decommissioned = [];   # decommissioned unt/capacity per generator (at each node)
        self.gen_operational = [];      # operational unt/capacity per generator (at each node)
        self.storage_capacity = [];     # storage charging and discharging capacity per each storage type (at each node)
        self.storage_level = [];        # storage energy level per each storage type (at each node)
        self.line_established = [];     # established line capacity between two nodes
        # self.RPS_contribution_per_period = []; 
        self.emissions_per_period = [];

        # cost components
        self.total_cost = [];           # total cost of the system
        self.gen_est_cost = [];         #  generation establishment cost
        self.line_est_cost = [];        # transmission line establishment cost
        self.storage_est_cost = [];     # storage establishment cost
        self.gen_FOM_cost = [];         # fixed operation and maintenance cost per generator
        self.line_FOM_cost = [];        # fixed operation and maintenance cost per line
        self.storage_FOM_cost = [];     # fixed operation and maintenance cost per storage
      
        # used in the Benders only
        self.MP_cost = [];
        self.theta = [];
        self.total_SP_cost = [];

class MP_Decision_Values(MP_Decision_Variables):
    def __init__(self): super().__init__();     


def define_MP_decision_variables(Model, DV, data, Setting):

    # define decision variables for investment
    DV.gen_established = Model.add_variables(range(data.num_generators), range(data.num_nodes), lb=0, domain=poi.VariableDomain.Continuous);    
    DV.gen_operational = Model.add_variables(range(data.num_generators), range(data.num_nodes), lb=0, domain=poi.VariableDomain.Continuous);    
    DV.gen_decommissioned = Model.add_variables(range(data.num_generators), range(data.num_nodes), lb=0, domain=poi.VariableDomain.Continuous);    
    
    for i in range(data.num_generators):
        if data.Generators[i].is_thermal and not Setting['relax_int_vars']:
            for n in range(data.num_nodes):DV.gen_established[i,n] = Model.add_variable(lb=0, domain=poi.VariableDomain.Integer);
            for n in range(data.num_nodes):DV.gen_operational[i,n] = Model.add_variable(lb=0, domain=poi.VariableDomain.Integer);
                        
        
    DV.storage_capacity = Model.add_variables(range(data.num_storages), range(data.num_nodes), lb=0, domain=poi.VariableDomain.Continuous);
    DV.storage_level = Model.add_variables(range(data.num_storages), range(data.num_nodes), lb=0, domain=poi.VariableDomain.Continuous);  
    DV.line_established = Model.add_variables(range(data.num_lines), lb=0, domain=poi.VariableDomain.Continuous);   
    # DV.RPS_contribution_per_period = Model.add_variables(range(data.num_rep_periods), lb=0, domain=poi.VariableDomain.Continuous);
    DV.emissions_per_period = Model.add_variables(range(data.num_rep_periods), lb=0, domain=poi.VariableDomain.Continuous);

    # cost components
    DV.MP_cost = Model.add_variable(lb=0, domain=poi.VariableDomain.Continuous);
    DV.gen_est_cost = Model.add_variable(lb=0, domain=poi.VariableDomain.Continuous);
    DV.line_est_cost = Model.add_variable(lb=0, domain=poi.VariableDomain.Continuous);
    DV.storage_est_cost = Model.add_variable(lb=0, domain=poi.VariableDomain.Continuous);
    DV.line_FOM_cost = Model.add_variable(lb=0, domain=poi.VariableDomain.Continuous);    
    DV.gen_FOM_cost = Model.add_variable(lb=0, domain=poi.VariableDomain.Continuous);
    DV.storage_FOM_cost = Model.add_variable(lb=0, domain=poi.VariableDomain.Continuous);

    DV.theta = Model.add_variables(range(data.num_rep_periods),lb=0, domain=poi.VariableDomain.Continuous);    # SP obj function approximation
    DV.total_SP_cost = Model.add_variable(lb=0, domain=poi.VariableDomain.Continuous);

def define_MP_objective(Model, DV, data, Setting):
    
    # define objective function

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

    # total subproblem cost approximation
    Model.add_linear_constraint(DV.total_SP_cost-poi.quicksum(DV.theta[s] for s in range(data.num_rep_periods)), poi.Eq, 0);

    # total cost
    Model.add_linear_constraint(DV.MP_cost-
                                DV.gen_est_cost- 
                                DV.gen_FOM_cost-
                                DV.line_est_cost - 
                                DV.line_FOM_cost - 
                                DV.storage_est_cost- 
                                DV.storage_FOM_cost-
                                DV.total_SP_cost,
                                poi.Eq, 0);

    return DV.MP_cost;

def MP_constraints(Model, DV, data, Setting):
        # add first stage constraints  
    # determine the operational generators  
    if Setting['is_green_field']:
        for g in range(data.num_generators):
            for n in range(data.num_nodes):                    
                Model.add_linear_constraint(DV.gen_operational[g,n]-DV.gen_established[g,n], poi.Eq, 0);
    else:
        for g in range(data.num_generators):
            for n in range(data.num_nodes):
                Model.add_linear_constraint(DV.gen_operational[g,n]-DV.gen_established[g,n]+DV.gen_decommissioned[g,n], poi.Eq, 0);

    # line expansion limits (commented out as no longer applies to the current study)
    # if Setting['expansion_allowed']:
    #     for l in range(data.num_lines):
    #         fn = data.Lines[l].from_node;
    #         tn = data.Lines[l].to_node;
    #         peak_loadf = np.max(data.Nodes[fn].demand[data.rep_hours]);
    #         peak_loadt = np.max(data.Nodes[tn].demand[data.rep_hours]);
    #         Model.add_linear_constraint(DV.line_established[l]-max(peak_loadf,peak_loadt)*Setting['line_limit_rate'], poi.Leq, 0);

    # land availability for renewables
    for g in range(data.num_generators):
        if data.Generators[g].Type=='wind-new':
            for n in range(data.num_nodes):
                Model.add_linear_constraint(DV.gen_operational[g,n], poi.Leq, data.Nodes[n].area_wind* data.Generators[g].power2area_density);            
        if data.Generators[g].Type=='solar-UPV':
            for n in range(data.num_nodes):
                Model.add_linear_constraint(DV.gen_operational[g,n], poi.Leq, data.Nodes[n].area_solar* data.Generators[g].power2area_density);

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


    # impose the duration range constraint
    for s in range(data.num_storages):
        for n in range(data.num_nodes):
            Model.add_linear_constraint(DV.storage_level[s,n]-
            data.Storages[s].duration_range* DV.storage_capacity[s,n], poi.Eq, 0);


    # RPS constraint, period-wise not time step (load-shedding variable should be period-wise as well)
    # Model.add_linear_constraint(poi.quicksum(DV.RPS_contribution_per_period[d] for d in range(data.num_rep_periods)) - 
    #        Setting['RPS'] * poi.quicksum(data.rep_hours_weights[t]*(data.Nodes[n].demand[data.rep_hours[t]] - DV.load_shedding[n,t]) for n in range(data.num_nodes) for t in range(data.num_rep_hours)),
    #        poi.Geq, 0);
    
    # emissions limit, period-wise not time step
    if Setting['Decarbonization_target'] > 0:
        Model.add_linear_constraint(poi.quicksum(DV.emissions_per_period[d] for d in range(data.num_rep_periods)) - (1-Setting['Decarbonization_target'])* Setting['ISONE_power_emission_1990']*1000, poi.Leq, 0);


def get_MP_variable_values(Model, DV, DV_values, data):
    # retrieve the values of the decision variables after solving the model
    DV_values.gen_operational = np.array([[Model.get_value(DV.gen_operational[g, n]) for n in range(data.num_nodes)] for g in range(data.num_generators)]);
    DV_values.storage_capacity = np.array([[Model.get_value(DV.storage_capacity[s, n]) for n in range(data.num_nodes)] for s in range(data.num_storages)]);
    DV_values.storage_level = np.array([[Model.get_value(DV.storage_level[s, n]) for n in range(data.num_nodes)] for s in range(data.num_storages)]);
    DV_values.line_established = np.array([Model.get_value(DV.line_established[l]) for l in range(data.num_lines)]);
    # DV_values.RPS_contribution_per_period = np.array([Model.get_value(DV.RPS_contribution_per_period[r]) for r in range(data.num_rep_periods)]);
    DV_values.emissions_per_period = np.array([Model.get_value(DV.emissions_per_period[d]) for d in range(data.num_rep_periods)]);
    DV_values.theta = np.array([Model.get_value(DV.theta[sp]) for sp in range(data.num_rep_periods)]);
    DV_values.total_SP_cost = Model.get_value(DV.total_SP_cost);
    DV_values.MP_cost = Model.get_value(DV.MP_cost);


    # calculate the left hand side of the optimality cut

def evaluate_cut_correctness(DV_Val, SP_duals, data, Setting):

    for sp in range(data.num_rep_periods):
        slice1 = np.arange(sp*Setting['hours_per_period'], (sp+1)*Setting['hours_per_period']);
        sp_hours = data.rep_hours[slice1];
        sp_hours_weights = data.rep_hours_weights[slice1];
        nT = len(sp_hours);
        lhs = DV_Val.theta[sp];
        for g in range(data.num_generators):
            for n in range(data.num_nodes):
                for t in range(nT):
                    if data.Generators[g].is_thermal:
                        lhs -= SP_duals[sp].prod_limit[g,n,t]*(data.Generators[g].nameplate_capacity*DV_Val.gen_operational[g,n]);
                    elif data.Generators[g].Type=='solar-UPV':
                        lhs -= SP_duals[sp].prod_limit[g,n,t]*(data.Nodes[n].solar_cf[sp_hours[t]]*data.Generators[g].nameplate_capacity*DV_Val.gen_operational[g,n]);
                    elif data.Generators[g].Type=='wind-new':
                        lhs -= SP_duals[sp].prod_limit[g,n,t]*(data.Nodes[n].wind_cf[sp_hours[t]]*data.Generators[g].nameplate_capacity*DV_Val.gen_operational[g,n]);

                    if t>0 and data.Generators[g].is_thermal:
                        lhs -= SP_duals[sp].ramp_limit_up[g,n,t]*(data.Generators[g].ramp_rate*data.Generators[g].nameplate_capacity*DV_Val.gen_operational[g,n]);
                        lhs -= SP_duals[sp].ramp_limit_down[g,n,t]*(data.Generators[g].ramp_rate*data.Generators[g].nameplate_capacity*DV_Val.gen_operational[g,n]);

        # Balance equation
        if Setting['is_copper_plate_approx']:
            for t in range(nT):
                rhs = 0;
                [rhs := rhs + data.Nodes[n].demand[sp_hours[t]] for n in range(data.num_nodes)];
                lhs -= SP_duals[sp].load_balance[t]*rhs;
        else:
            for n in range(data.num_nodes):
                for t in range(nT):                                
                    lhs -= SP_duals[sp].load_balance[n,t]*data.Nodes[n].demand[sp_hours[t]];

        # flow
        if not Setting['is_copper_plate_approx']:
            for l in range(data.num_lines):
                for t in range(nT):
                    lhs -= SP_duals[sp].flow_limit1[l,t]*DV_Val.line_established[l];
                    lhs -= SP_duals[sp].flow_limit2[l,t]*DV_Val.line_established[l];
        
        # storage
        for s in range(data.num_storages):                
            for n in range(data.num_nodes):
                lhs -= SP_duals[sp].storage_SOC_balance[n]*(DV_Val.storage_level[s,n]/2);
                for t in range(nT):
                    lhs -= SP_duals[sp].storage_charge_limit[n,t]*DV_Val.storage_capacity[s,n];
                    lhs -= SP_duals[sp].storage_discharge_limit[n,t]*DV_Val.storage_capacity[s,n];
                    lhs -= SP_duals[sp].storage_SOC_limit[n,t]*DV_Val.storage_level[s,n];   
        # emissions limit 
        if Setting['Decarbonization_target'] > 0:       
            lhs -= SP_duals[sp].emissions_limit*DV_Val.emissions_per_period[sp];
         
        # print(f'theta - sp_obj:  {round(lhs)}');

def add_optimality_cut(Model, DV, SP_duals, data, Setting, sp):
    slice1 = np.arange(sp*Setting['hours_per_period'], (sp+1)*Setting['hours_per_period']);
    sp_hours = data.rep_hours[slice1];
    sp_hours_weights = data.rep_hours_weights[slice1];
    nT = len(sp_hours);
    
    lhs = poi.ExprBuilder();
    lhs += DV.theta[sp];

    # temrs from production limit and ramping constraints
    for g in range(data.num_generators):
        for n in range(data.num_nodes):
            for t in range(nT):
                if data.Generators[g].is_thermal:
                    lhs -= SP_duals.prod_limit[g,n,t]*(data.Generators[g].nameplate_capacity*DV.gen_operational[g,n]);
                elif data.Generators[g].Type=='solar-UPV':
                    lhs -= SP_duals.prod_limit[g,n,t]*(data.Nodes[n].solar_cf[sp_hours[t]]*data.Generators[g].nameplate_capacity*DV.gen_operational[g,n]);
                elif data.Generators[g].Type=='wind-new':
                    lhs -= SP_duals.prod_limit[g,n,t]*(data.Nodes[n].wind_cf[sp_hours[t]]*data.Generators[g].nameplate_capacity*DV.gen_operational[g,n]);

                if t>0 and data.Generators[g].is_thermal:
                    lhs -= SP_duals.ramp_limit_up[g,n,t]*(data.Generators[g].ramp_rate*data.Generators[g].nameplate_capacity*DV.gen_operational[g,n]);
                    lhs -= SP_duals.ramp_limit_down[g,n,t]*(data.Generators[g].ramp_rate*data.Generators[g].nameplate_capacity*DV.gen_operational[g,n]);
    # Balance equation
    if Setting['is_copper_plate_approx']:
        for t in range(nT):
            rhs = 0;
            [rhs := rhs + data.Nodes[n].demand[sp_hours[t]] for n in range(data.num_nodes)];
            lhs -= SP_duals.load_balance[t]*rhs;
    else:
        for n in range(data.num_nodes):
            for t in range(nT):                                
                lhs -= SP_duals.load_balance[n,t]*data.Nodes[n].demand[sp_hours[t]];

    # flow
    if not Setting['is_copper_plate_approx']:
        for l in range(data.num_lines):
            for t in range(nT):
                lhs -= SP_duals.flow_limit1[l,t]*DV.line_established[l];
                lhs -= SP_duals.flow_limit2[l,t]*DV.line_established[l];
    
    # storage
    for s in range(data.num_storages):                
        for n in range(data.num_nodes):
            lhs -= SP_duals.storage_SOC_balance[n]*(DV.storage_level[s,n]/2);
            for t in range(nT):
                lhs -= SP_duals.storage_charge_limit[n,t]*DV.storage_capacity[s,n];
                lhs -= SP_duals.storage_discharge_limit[n,t]*DV.storage_capacity[s,n];
                lhs -= SP_duals.storage_SOC_limit[n,t]*DV.storage_level[s,n];    
    # emissions limit
    if Setting['Decarbonization_target'] > 0:
        lhs -= SP_duals.emissions_limit*DV.emissions_per_period[sp];


    Model.add_linear_constraint(lhs, poi.Geq, 0);
    # Model.cb_add_lazy_constraint(lhs, poi.Geq, 0);


def print_some_variables(DV_values, data):
        # print some of the values
    for g in range(data.num_generators):
        for n in range(data.num_nodes):
            if DV_values.gen_operational[g,n] > 0.5:
                print(f'gen_op[{g},{n}] = {round(DV_values.gen_operational[g,n])}');
    for s in range(data.num_storages):
        for n in range(data.num_nodes):
            if DV_values.storage_level[s,n] > 0.5:
                print(f'storage_level[{s},{n}] = {round(DV_values.storage_level[s,n])}');
            if DV_values.storage_capacity[s,n] >0.5:
                print(f'storage_capacity[{s},{n}] = {round(DV_values.storage_capacity[s,n])}');
    for l in range(data.num_lines):
        if DV_values.line_established[l] > 0.5:
            print(f'line_established[{l}] = {round(DV_values.line_established[l])}');
    print(f'total SP cost {DV_values.total_SP_cost}');
    # for d in range(data.num_rep_periods):
    #     if DV_values.RPS_contribution_per_period[d] > 0:
    #         print(f'RPS_contribution_per_period[{d}] = {DV_values.RPS_contribution_per_period[d]}');
    for d in range(data.num_rep_periods):
        if DV_values.emissions_per_period[d] > 0:
            print(f'emissions_per_period[{d}] = {DV_values.emissions_per_period[d]}');



