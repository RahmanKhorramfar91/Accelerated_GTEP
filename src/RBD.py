'''
Bismillah

implmentation of Regularized Benders from:

"Pecci, F., & Jenkins, J. D. (2025). 
Regularized benders decomposition for high performance capacity expansion models. 
IEEE Transactions on Power Systems, 40(4), 3105-3116."
'''

import numpy as np;
import time; 
import pyoptinterface as poi;
from pyoptinterface import gurobi;
from pyoptinterface import highs;
import Setting
import src.DV_Classes as DV_Classes;
import src.Define_DVs as Define_DVs;
import src.Constraints as Constraints;
import src.Objective_Function as Objective_Function;
import src.Get_Vals as Get_Vals;
import src.Print_Outcomes as Print_Outcomes;
import src.BD_MP as BD_MP;
import src.BD_SP as BD_SP;

class RBD():

    def __init__(self):
        pass;

    def RBD_run(self, data, Setting):
        if Setting['solver']=='gurobi':
            MP_model = gurobi.Model();
        if Setting['solver'] == 'highs':
            MP_model = highs.Model();   
        MP_DV = BD_MP.MP_Decision_Variables();
        MP_DV_values = BD_MP.MP_Decision_Values();
        MP_model.set_raw_parameter('OutputFlag', Setting['show_log_info']); 
        BD_MP.define_MP_decision_variables(MP_model, MP_DV, data, Setting);
        MP_cost = BD_MP.define_MP_objective(MP_model, MP_DV, data, Setting);
        # set the objective function                                 
        MP_model.set_objective(MP_cost, poi.ObjectiveSense.Minimize);
        BD_MP.MP_constraints(MP_model, MP_DV, data, Setting);       
        # MP_model.set_raw_parameter('LazyConstraints', 1);
        MP_model.optimize();
        BD_MP.get_MP_variable_values(MP_model, MP_DV, MP_DV_values, data);

        # print(MP_model.get_model_attribute(poi.ModelAttribute.TerminationStatus));
        # print(f'MP Objective value: {np.round(MP_model.get_value(MP_cost),2)}');
        LB, UB = 0, 1e15;
        LB = MP_DV_values.MP_cost;

        # the main loop
        for iter in range(1):
            # build the subproblem models
            SP_duals = [[] for _ in range(data.num_rep_periods)];
            stage2_obj = 0;
            for si in range(data.num_rep_periods): # solve subproblems in sequence, but they can be solved in parallel
                SP_duals[si], SP_boj= BD_SP.solve_SP_model(MP_DV_values, data, Setting, si);
                stage2_obj += SP_boj;

                # add the cut to the MP
                BD_MP.add_optimality_cut(MP_model, MP_DV, SP_duals[si], data, Setting, si);
            
            MP_model.set_objective(MP_cost, poi.ObjectiveSense.Minimize);
            MP_model.optimize();
            # print('MP Status: ', MP_model.get_model_attribute(poi.ModelAttribute.TerminationStatus));
            BD_MP.get_MP_variable_values(MP_model, MP_DV, MP_DV_values, data);
            # BD_MP.print_some_variables(MP_DV_values, data)
            # BD_MP.evaluate_cut_correctness(MP_DV_values, SP_duals, data, Setting);
            LB = MP_DV_values.MP_cost;
            

            print(f'iter: {iter}, LB: {round(LB/1e7)}e7, UB: {round(UB/1e7)}e7, gap: {round((UB-LB)/UB*100,2)}%');

            if abs((UB-LB)/UB)<0.01:
                print(f'optimal solution found');
                break;
            else:
                MP_model, MP_DV_values = self.solve_regularized_MP(MP_model, MP_DV, MP_DV_values, UB, LB, data, MP_cost, Setting);
                UB = self.get_UB(MP_DV_values, stage2_obj, data,UB);
            
            # print(f'iter: {iter}, MP Objective value: {np.round(MP_model.get_value(MP_cost),2)}');
            # print(f'iter: {iter}, SP cost in the MP: {np.round(MP_model.get_value(MP_DV.total_SP_cost),2)}');

    def get_UB(self, MP_DV_values, stage2_obj, data,UB):

        UB_temp = MP_DV_values.MP_cost;
        for sp in range(data.num_rep_periods):
            UB_temp -= MP_DV_values.theta[sp];
        if UB_temp + stage2_obj < UB:
             UB = UB_temp + stage2_obj;

        return UB;


    def solve_regularized_MP(self, MP_model, MP_DV, MP_DV_values, UB, LB, data,MP_cost, Setting):
        alpha = 0.5; # regularization parameter, needs to be tuned
        # set the objective function to a constant scalar (feasibility problem)
        MP_model.set_objective(0, poi.ObjectiveSense.Minimize);
        # BD_MP.MP_constraints(MP_model, MP_DV, data, Setting);

        ## add regularization term to the 
        # MP_cost = BD_MP.define_MP_objective(MP_model, MP_DV, data, Setting);

        # calculate L_k
        LB = LB + alpha*(UB-LB);
        # add regularization constraint
        reg_const = MP_model.add_linear_constraint(MP_cost, poi.Leq, LB);
        MP_model.set_raw_parameter('Method', 2);
        MP_model.set_raw_parameter('Crossover', 0); 
        # MP_model.set_raw_parameter('MIPGap', Setting['solver_gap']);

        MP_model.optimize();

        # print(MP_model.get_model_attribute(poi.ModelAttribute.TerminationStatus));
        
        BD_MP.get_MP_variable_values(MP_model, MP_DV, MP_DV_values, data);
        MP_model.delete_constraint(reg_const);
        # BD_MP.print_some_variables(MP_DV_values, data);
        return MP_model, MP_DV_values;

