# -*- coding: utf-8 -*-
"""
Bismillah
Created on Thursday 31 July 16:07 2025  

The model is implemented for green frield only. 

@author: Rahman Khorramfar  
"""
import numpy as np;
import time; 
import pyoptinterface as poi;
from pyoptinterface import gurobi;
from pyoptinterface import highs;
import src.DV_Classes as DV_Classes;
import src.Define_DVs as Define_DVs;
import src.Constraints as Constraints;
import src.Objective_Function as Objective_Function;
import src.Get_Vals as Get_Vals;
import src.Print_Outcomes as Print_Outcomes;


class Power_System_Model():

    def __init__(self, data, Setting):
        self.data = data;
        self.Setting = Setting;
        self.Model = [];
        self.DVi = DV_Classes.Power_System_Investment_Decision_Variables();
        self.DVo = DV_Classes.Power_System_Operational_Decision_Variables();
        self.DVi_values = DV_Classes.Power_System_Investment_Decision_Values();
        self.DVo_values = DV_Classes.Power_System_Operational_Decision_Values();
        self.Con = DV_Classes.Oper_Constraints_Names(data);
        self.Duals = DV_Classes.Dual_vals(data);

    def build_model(self):
        if self.Setting['solver']=='gurobi':
            self.Model = gurobi.Model();
        if self.Setting['solver'] == 'highs':
            self.Model = highs.Model();
        Define_DVs.define_investment_decision_variables(self.Model, self.DVi, self.data, self.Setting);
        Define_DVs.define_operational_decision_variables(self.Model, self.DVo, self.data.num_rep_hours, self.data);
        Objective_Function.define_extensive_form_objective(self.Model, self.DVi, self.DVo, self.data, self.Setting);
        self.add_investment_constraints();          
        self.add_operation_constraints();

    
    def solve_EF_model(self):
        # solve the model using the specified solver
        self.Model.set_raw_parameter('Timelimit', self.Setting['wall_clock_time_lim']);
        # self.Model.set_raw_parameter('Threads', self.Setting['solver_thread_num']);
        if self.Setting['Cross_over_status']==0:
            # self.Model.set_raw_parameter('Presolve', -1);
            # self.Model.set_raw_parameter('CrossoverBasis', 0);
            self.Model.set_raw_parameter('Method', 2);
            self.Model.set_raw_parameter('Crossover', 0);
            # self.Model.set_raw_parameter('BarHomogeneous', 1); 
        self.Model.set_raw_parameter('MIPGap', self.Setting['solver_gap']);
        self.Model.set_raw_parameter('LogFile', 'log.txt');
        self.Model.set_raw_parameter('LogToConsole', self.Setting['show_log_info']);
        # solve the model
        self.Model.optimize();
        
        print(self.Model.get_model_attribute(poi.ModelAttribute.TerminationStatus));
        # print(f'relative gap: {self.Model.get_model_attribute(poi.ModelAttribute.RelativeGap)}')
        print(f'Objective value: {np.round(self.Model.get_model_attribute(poi.ModelAttribute.ObjectiveValue),2)}');

    def add_investment_constraints(self):        
        Constraints.inv_const_num_operational_generators(self.Model, self.DVi, self.data, self.Setting);
        # Constraints.inv_const_line_expansion_limits(self.Model, self.DV, self.data, self.Setting);
        Constraints.inv_const_land_availability_for_renewables(self.Model, self.DVi, self.data);
        Constraints.inv_const_CRM(self.Model, self.DVi, self.data, self.Setting);
        Constraints.inv_storage_duaration_range(self.Model, self.DVi, self.data);
        Constraints.inv_const_RPS(self.Model, self.DVi, self.data, self.Setting);  # over periods, not per time step
        Constraints.inv_const_emissions_limit(self.Model, self.DVi, self.data, self.Setting); # over periods, not per time step

    def add_operation_constraints(self):       
        Constraints.oper_const_production_limits(self.Model, self.DVi, self.DVo, self.Con, self.DVi_values, self.data.rep_hours, self.data, self.Setting); 
        Constraints.oper_const_ramping(self.Model, self.DVi, self.DVo, self.DVi_values, self.Con, self.data.num_rep_hours, self.data, self.Setting);          
        Constraints.oper_const_balance_equation(self.Model, self.DVo, self.Con, self.data.rep_hours, self.data, self.Setting);
        Constraints.oper_const_flow_limits(self.Model, self.DVi, self.DVo, self.DVi_values, self.Con, self.data.num_rep_hours, self.data, self.Setting); 
        # Constraints.oper_const_RPS(self.Model, self.DVi, self.DVo, self.data, self.Setting); 
        Constraints.oper_const_emissions_limit(self.Model, self.DVi, self.DVo, self.DVi_values, self.Con, range(self.data.num_rep_periods), self.data.rep_hours_weights, self.data, self.Setting); 
        Constraints.oper_const_storage(self.Model, self.DVi, self.DVo, self.DVi_values, self.Con, self.data.num_rep_hours, self.data, self.Setting);
    
    def get_DV_values(self):
        Get_Vals.get_investment_variable_values(self.Model, self.DVi, self.DVi_values, self.data);
        Get_Vals.get_operational_variable_values(self.Model, self.DVo, self.DVo_values, self.data.num_rep_hours, self.data);

    def print_results(self, start_time,RAM_MB):
        Print_Outcomes.publish_summary(self.DVi_values, self.DVo_values, [], [],[], self.data, self.Setting, start_time, self.Model.get_model_attribute(poi.ModelAttribute.RelativeGap), RAM_MB);
        if self.Setting['print_extensive_outcome']:
            Print_Outcomes.publish_extensive_form(self.DVi_values, self.DVo_values, self.Duals, self.data, self.Setting);


    def get_constraint_duals(self):
        Get_Vals.get_dual_values(self.Model, self.Con, self.Duals, self.data, self.Setting);

    


























