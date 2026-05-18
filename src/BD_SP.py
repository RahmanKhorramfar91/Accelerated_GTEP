# -*- coding: utf-8 -*-
"""
Bismillah
Created on Tuesday, 7 August 15:22 2025  
Revised on May 11, 8:21am, 2026
implementation of the subproblems for the multi cut Benders in which each period is a subproblem

@author: Rahman Khorramfar
"""
import numpy as np;
import pyoptinterface as poi;
from pyoptinterface import gurobi;
from pyoptinterface import highs;
import src.Define_DVs as Define_DVs;

def solve_SP_model(FS_Vals, data, Setting, sp):

    '''
    build the subproblem s with all its decision variables and constraints 

    Arg: SP_model, 
        FS_vals: value of the first-stage variables
        data, Setting,
        sp: the subproblem index

    Return: Model
    '''
    slice1 = np.arange(sp*Setting['hours_per_period'], (sp+1)*Setting['hours_per_period']);
    sp_hours = data.rep_hours[slice1];
    sp_hours_weights = data.rep_hours_weights[slice1];
    nT = len(sp_hours);

    if Setting['solver']=='gurobi':
        Model = gurobi.Model();
    if Setting['solver'] == 'highs':
        Model = highs.Model(); 
    DV = SP_Decision_Variables(); # declare SP variables
    # DV_values = SP_Decision_Values(); # declare SP variable values
    Con = SP_Constraints_Names(data); # declare SP constraints
    duals= SP_Dual_vals(data); # declare SP dual values
    Model.set_raw_parameter('OutputFlag', Setting['show_log_info']); 
    Model.set_raw_parameter('Method', 2);
    Model.set_raw_parameter('Crossover', 0);
    define_SP_decision_variables(Model, DV, data, nT); # define SP variables
    define_SP_objective(Model, DV, data, Setting, nT, sp_hours_weights); # define SP objective function

    SP_constraints(Model, DV,Con, FS_Vals, data, Setting, nT, sp_hours, sp_hours_weights, sp); # define SP constraints


    Model.optimize();

    # print(Model.get_model_attribute(poi.ModelAttribute.TerminationStatus));
    if Model.get_model_attribute(poi.ModelAttribute.TerminationStatus)==poi.TerminationStatusCode.OPTIMAL:
        print(f'SP {sp} Objective value: {np.round(Model.get_value(DV.SP_cost),2)}, shedding: {np.round(Model.get_value(DV.load_shedding_cost),2)}, fuel: {np.round(Model.get_value(DV.gas_fuel_cost),2)}, VOM: {np.round(Model.get_value(DV.VOM_cost),2)}');
    get_SP_dual_values(Model, Con, duals, data, Setting, sp);
    slice1 = np.arange(sp*Setting['hours_per_period'], (sp+1)*Setting['hours_per_period']);
    sp_hours = data.rep_hours[slice1];
    sp_hours_weights = data.rep_hours_weights[slice1];
    nT = len(sp_hours);
    # objective of the dual problem
    dual_obj=0;
    for n in range(data.num_nodes):
        for t in range(nT):
            for g in range(data.num_generators):
                if data.Generators[g].is_thermal:
                    dual_obj += duals.prod_limit[g, n,t]*(data.Generators[g].nameplate_capacity*FS_Vals.gen_operational[g,n]);
                if data.Generators[g].Type=='solar-UPV':
                    dual_obj += duals.prod_limit[g, n,t]*(data.Nodes[n].solar_cf[sp_hours[t]]*data.Generators[g].nameplate_capacity*FS_Vals.gen_operational[g,n]);  
                if data.Generators[g].Type=='wind-new':
                    dual_obj += duals.prod_limit[g, n,t]*(data.Nodes[n].wind_cf[sp_hours[t]]*data.Generators[g].nameplate_capacity*FS_Vals.gen_operational[g,n]);   
            
                if t>0 and data.Generators[g].is_thermal:
                    dual_obj += duals.ramp_limit_up[g,n,t]*(data.Generators[g].ramp_rate*data.Generators[g].nameplate_capacity*FS_Vals.gen_operational[g,n]);
                    dual_obj += duals.ramp_limit_down[g,n,t]*(data.Generators[g].ramp_rate*data.Generators[g].nameplate_capacity*FS_Vals.gen_operational[g,n]);
    # balance equation
    if Setting['is_copper_plate_approx']:
        for t in range(nT):
            rhs = 0;
            [rhs := rhs + data.Nodes[n].demand[sp_hours[t]] for n in range(data.num_nodes)];
            dual_obj += duals.load_balance[t]*rhs;
    else:
        for n in range(data.num_nodes):
            for t in range(nT):            
                dual_obj += duals.load_balance[n,t]*data.Nodes[n].demand[sp_hours[t]];
    
    # flow
    if not Setting['is_copper_plate_approx']:
        for l in range(data.num_lines):
            for t in range(nT):
                dual_obj += duals.flow_limit1[l,t]*FS_Vals.line_established[l];
                dual_obj += duals.flow_limit2[l,t]*FS_Vals.line_established[l];
    
    # storage
    for n in range(data.num_nodes):
        dual_obj += duals.storage_SOC_balance[n]*(FS_Vals.storage_level[0,n]/2);
        for t in range(nT):
            dual_obj += duals.storage_charge_limit[n,t]*FS_Vals.storage_capacity[0,n];
            dual_obj += duals.storage_discharge_limit[n,t]*FS_Vals.storage_capacity[0,n];
            dual_obj += duals.storage_SOC_limit[n,t]*FS_Vals.storage_level[0,n];    
    # emissions limit
    dual_obj += duals.emissions_limit*FS_Vals.emissions_per_period[sp];


    # print(f'SP {sp} dual objective: {dual_obj}');

    # print load shedding amount at each node
    for n in range(data.num_nodes):
        shed_node = 0;
        for t in range(nT):
            shed_node += Model.get_value(DV.load_shedding[n,t]);
        # print(f'load shedding at node {n} is {shed_node}');
    return duals, Model.get_value(DV.SP_cost);


def SP_constraints(Model, DV, Con, FS_Vals, data, Setting, nT, sp_hours, sp_hours_weights, sp=-1):

    # production limits for each generator type at each node at each time period
    Con.prod_limit =np.empty((data.num_generators, data.num_nodes, nT), dtype=object);
    for g in range(data.num_generators):
        for n in range(data.num_nodes):
            for t in range(nT):
                if data.Generators[g].is_thermal:
                    Con.prod_limit[g,n,t] = Model.add_linear_constraint(DV.generation[g,n,t], poi.Leq, data.Generators[g].nameplate_capacity*FS_Vals.gen_operational[g,n]);
                elif data.Generators[g].Type=='solar-UPV':
                    Con.prod_limit[g,n,t] = Model.add_linear_constraint(DV.generation[g,n,t], poi.Leq, data.Nodes[n].solar_cf[sp_hours[t]]*data.Generators[g].nameplate_capacity*FS_Vals.gen_operational[g,n]);
                elif data.Generators[g].Type=='wind-new':
                    Con.prod_limit[g,n,t] = Model.add_linear_constraint(DV.generation[g,n,t], poi.Leq, data.Nodes[n].wind_cf[sp_hours[t]]*data.Generators[g].nameplate_capacity*FS_Vals.gen_operational[g,n]);

    # ramping
    Con.ramp_limit_up = np.empty((data.num_generators, data.num_nodes, nT), dtype=object);
    Con.ramp_limit_down = np.empty((data.num_generators, data.num_nodes, nT), dtype=object);
    for g in range(data.num_generators):
        for n in range(data.num_nodes):
            for t in range(1, nT):
                if data.Generators[g].is_thermal:
                    Con.ramp_limit_up[g,n,t] = Model.add_linear_constraint(DV.generation[g,n,t]-DV.generation[g,n,t-1], poi.Leq,data.Generators[g].ramp_rate*data.Generators[g].nameplate_capacity*FS_Vals.gen_operational[g,n]);
                    Con.ramp_limit_down[g,n,t] = Model.add_linear_constraint(-DV.generation[g,n,t]+DV.generation[g,n,t-1], poi.Leq, data.Generators[g].ramp_rate*data.Generators[g].nameplate_capacity*FS_Vals.gen_operational[g,n]);

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
                
    # flow constraints
    if not Setting['is_copper_plate_approx']:
        Con.flow_limit1 = np.empty((data.num_lines, nT), dtype=object);
        Con.flow_limit2 = np.empty((data.num_lines, nT), dtype=object);
        for l in range(data.num_lines):
            for t in range(nT):
                if not data.Lines[l].is_existing:
                    Con.flow_limit1[l,t] = Model.add_linear_constraint(DV.flow[l,t], poi.Leq, FS_Vals.line_established[l]);
                    Con.flow_limit2[l,t] = Model.add_linear_constraint(-DV.flow[l,t], poi.Leq, FS_Vals.line_established[l]);

    # renewable portfolio standard
    # if Setting['RPS'] > 0:
    #     Con.RPS = Model.add_linear_constraint(
    #         poi.quicksum(sp_hours_weights[t]*DV.generation[g,n,t]
    #         for g in range(data.num_generators) 
    #         for n in range(data.num_nodes) 
    #         for t in range(nT) if data.Generators[g].Type in ['solar-UPV', 'wind-new']),
    #         poi.Qeq, FS_Vals.RPS_contribution[sp]);

    # Emissions limit
    # Con.emissions_limit = np.empty(dtype=object);
    if Setting['Decarbonization_target'] > 0 and sp != -1:
        Con.emissions_limit = Model.add_linear_constraint(
             poi.quicksum(sp_hours_weights[t]*DV.generation[g,n,t]*data.Generators[g].heat_rate*data.Generators[g].emission_kg_per_MMBtu
            for g in range(data.num_generators) 
            for n in range(data.num_nodes) 
            for t in range(nT) if data.Generators[g].is_thermal),
            poi.Leq, FS_Vals.emissions_per_period[sp]);
    elif sp==-1:# thus this is the entire operational problem, so traverse over all subproblems
        for d in range(data.num_rep_periods):
            Con.emissions_limit = Model.add_linear_constraint(
                poi.quicksum(sp_hours_weights[t]*DV.generation[g,n,t]*data.Generators[g].heat_rate*data.Generators[g].emission_kg_per_MMBtu
                for g in range(data.num_generators) 
                for n in range(data.num_nodes) 
                for t in range(nT) if data.Generators[g].is_thermal),
                poi.Leq, FS_Vals.emissions_per_period[d]);


    # storage constraints    
    Con.storage_SOC_balance = np.empty((data.num_nodes), dtype=object);
    Con.storage_charge_limit = np.empty((data.num_nodes, nT), dtype=object);
    Con.storage_discharge_limit = np.empty((data.num_nodes, nT), dtype=object);
    Con.storage_SOC_limit = np.empty((data.num_nodes, nT), dtype=object);
    for s in range(data.num_storages):
        for n in range(data.num_nodes):
            for t in range(nT):
                if t>0:
                    Model.add_linear_constraint(DV.SOC[s,n,t]-(1-data.Storages[s].self_discharge)*DV.SOC[s,n,t-1] -
                    data.Storages[s].charging_eff*DV.storage_charge[s,n,t] +
                    DV.storage_discharge[s,n,t]/data.Storages[s].discharging_eff,
                    poi.Eq, 0);
                else:
                    Con.storage_SOC_balance[n] = Model.add_linear_constraint(DV.SOC[s,n,t], poi.Eq, FS_Vals.storage_level[s,n]/2);
                
                Con.storage_charge_limit[n,t] = Model.add_linear_constraint(DV.storage_charge[s,n,t], poi.Leq, FS_Vals.storage_capacity[s,n]);
                Con.storage_discharge_limit[n,t] = Model.add_linear_constraint(DV.storage_discharge[s,n,t], poi.Leq, FS_Vals.storage_capacity[s,n]);
                Con.storage_SOC_limit[n,t] = Model.add_linear_constraint(DV.SOC[s,n,t], poi.Leq, FS_Vals.storage_level[s,n]);

    # calculate emissions for each generator at each node at each time period
    emis_expr = poi.ExprBuilder();
    for g in range(data.num_generators):
        if data.Generators[g].is_thermal:
            for n in range(data.num_nodes):
                for t in range(nT):
                    emis_expr += sp_hours_weights[t]* data.Generators[g].emission_kg_per_MMBtu*data.Generators[g].heat_rate * DV.generation[g,n,t];

    Model.add_linear_constraint(DV.total_CO2_emissions_kg - emis_expr, poi.Eq, 0);


class SP_Decision_Variables:
    def __init__(self):     
        # set of operational decision variables
        self.generation = [];           # generation per generator per time period (at each node)
        self.load_shedding = [];        # load shedding per time period (at each node)
        self.storage_charge = [];       # storage charging amount per each storage type per each time period (at each node)
        self.storage_discharge = [];    # storage charging amount per each storage type per each time period (at each node)
        self.SOC = [];                  # state of charge per each storage type per each time period (at each node)
        self.flow = [];                 # electric power flow per line per time period (between two nodes)

        # cost components
        self.SP_cost = [];           # total cost of the system
        self.VOM_cost = [];             # variable operation and maintenance cost
        self.load_shedding_cost = [];   # load shedding cost
        self.gas_fuel_cost = [];        # gas fuel cost

        # other decision variables
        self.total_CO2_emissions_kg = [];  # total CO2 emissions in kg

class SP_Decision_Values(SP_Decision_Variables):
    def __init__(self): super().__init__();     

def define_SP_decision_variables(Model, DV, data, nT):

    # define decision variables for operation
    DV.generation = Model.add_variables(range(data.num_generators), range(data.num_nodes), range(nT), lb=0, domain=poi.VariableDomain.Continuous);
    DV.load_shedding = Model.add_variables(range(data.num_nodes), range(nT), lb=0, domain=poi.VariableDomain.Continuous);
    DV.storage_charge = Model.add_variables(range(data.num_storages), range(data.num_nodes), range(nT), lb=0, domain=poi.VariableDomain.Continuous);
    DV.storage_discharge = Model.add_variables(range(data.num_storages), range(data.num_nodes), range(nT), lb=0, domain=poi.VariableDomain.Continuous);
    DV.SOC = Model.add_variables(range(data.num_storages), range(data.num_nodes), range(nT), lb=0, domain=poi.VariableDomain.Continuous);
    DV.flow = Model.add_variables(range(data.num_lines), range(nT),  domain=poi.VariableDomain.Continuous);

    # cost components
    DV.SP_cost = Model.add_variable(lb=0, domain=poi.VariableDomain.Continuous);
    DV.VOM_cost = Model.add_variable(lb=0, domain=poi.VariableDomain.Continuous);
    DV.load_shedding_cost = Model.add_variable(lb=0, domain=poi.VariableDomain.Continuous);
    DV.gas_fuel_cost = Model.add_variable(lb=0, domain=poi.VariableDomain.Continuous);    

    # other decision variables
    DV.total_CO2_emissions_kg = Model.add_variable(lb=0, domain=poi.VariableDomain.Continuous);

def define_SP_objective(Model, DV, data, Setting, nT, sp_hours_weights):
    
    # slice1 = np.arange(sp*Setting['hours_per_period'], (sp+1)*Setting['hours_per_period']);
    # sp_hours = data.rep_hours[slice1];
    # nT = len(sp_hours);

    # geneneration variable operation and maintenance cost
    Model.add_linear_constraint(DV.VOM_cost-poi.quicksum(sp_hours_weights[t]* data.Generators[g].VOM_per_MWh * DV.generation[g, n, t] for g in range(data.num_generators) for n in range(data.num_nodes) for t in range(nT)), poi.Eq, 0);

    # load shedding cost
    Model.add_linear_constraint(DV.load_shedding_cost-poi.quicksum(sp_hours_weights[t]*DV.load_shedding[n, t] * Setting['load_shedding_penalty'] for n in range(data.num_nodes) for t in range(nT)), poi.Eq, 0);

    # gas fuel cost
    Model.add_linear_constraint(DV.gas_fuel_cost-poi.quicksum(sp_hours_weights[t]*data.Generators[g].heat_rate* DV.generation[g, n, t] * Setting['NG_price'] for g in range(data.num_generators) for n in range(data.num_nodes) for t in range(nT) if data.Generators[g].is_thermal), poi.Eq, 0);  

    # total cost
    Model.add_linear_constraint(DV.SP_cost-
                                DV.VOM_cost - 
                                DV.load_shedding_cost - 
                                DV.gas_fuel_cost, 
                                poi.Eq, 0);

    # set the objective function                                 
    Model.set_objective(DV.SP_cost, poi.ObjectiveSense.Minimize);


class SP_Constraints_Names:
    def __init__(self, data):
        self.prod_limit = [];
        self.load_balance = [];
        self.ramp_limit_up = [];
        self.ramp_limit_down = [];
        self.flow_limit1 = [];
        self.flow_limit2 = [];
        self.storage_SOC_balance = [];
        self.storage_charge_limit = [];
        self.storage_discharge_limit = [];
        self.storage_SOC_limit = [];
        self.RPS = [];
        self.CRM = [];
        self.land_availability = [];
        # self.line_expansion_limit = [];
        self.emissions_limit = [];



class SP_Dual_vals(SP_Constraints_Names):
    def __init__(self, data=None): super().__init__(data);


def get_SP_dual_values(Model, Con, Duals, data, Setting, sp):
    slice1 = np.arange(sp*Setting['hours_per_period'], (sp+1)*Setting['hours_per_period']);
    sp_hours = data.rep_hours[slice1];
    sp_hours_weights = data.rep_hours_weights[slice1];
    nT = len(sp_hours);

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

            # if Duals.prod_limit_thermal[n,t]!=0:
            #     print(f'dual prod limit thermal [{n},{t}] = {Duals.prod_limit_thermal[n,t]}');
            #     break;
            # if Duals.prod_limit_solar[n,t]!=0:
            #     print(f'dual prod limit solar [{n},{t}] = {Duals.prod_limit_solar[n,t]}');
            #     break;
            # if Duals.prod_limit_wind[n,t]!=0:
            #     print(f'dual prod limit wind [{n},{t}] = {Duals.prod_limit_wind[n,t]}');
            #     break;

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
        Duals.emissions_limit = Model.get_constraint_attribute(Con.emissions_limit, poi.ConstraintAttribute.Dual);

def get_SP_values(Model, DV, data, Setting, sp):
    pass;

def solve_operational_problem(FS_Vals, data, Setting):
    if Setting['solver']=='gurobi':
        Model = gurobi.Model();
    if Setting['solver'] == 'highs':
        Model = highs.Model();  
    sp_hours = data.rep_hours;
    sp_hours_weights = data.rep_hours_weights;
    nT = len(sp_hours);

    DV = SP_Decision_Variables(); # declare SP variables
    DV_values = SP_Decision_Values(); # declare SP variable values
    Con = SP_Constraints_Names(data); # declare SP constraints
    Model.set_raw_parameter('OutputFlag', Setting['show_log_info']); 
    Model.set_raw_parameter('Method', 2);
    Model.set_raw_parameter('Crossover', 0);
    define_SP_decision_variables(Model, DV, data, nT); # define SP variables
    define_SP_objective(Model, DV, data, Setting, nT, sp_hours_weights); # define SP objective function

    SP_constraints(Model, DV,Con, FS_Vals, data, Setting,  nT, sp_hours, sp_hours_weights); # define SP constraints


    Model.optimize();
    print(f'Operational problem objective value: {np.round(Model.get_value(DV.SP_cost),2)}, shedding: {np.round(Model.get_value(DV.load_shedding_cost),2)}, fuel: {np.round(Model.get_value(DV.gas_fuel_cost),2)}, VOM: {np.round(Model.get_value(DV.VOM_cost),2)}');

    # print(Model.get_model_attribute(poi.ModelAttribute.TerminationStatus));

