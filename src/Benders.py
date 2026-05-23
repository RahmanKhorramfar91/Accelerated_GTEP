'''
Bismillah
May 18, 2026 at 19:37, Cambriedge home
implmentation of Regularized Benders from:


"Pecci, F., & Jenkins, J. D. (2025). 
Regularized benders decomposition for high performance capacity expansion models. 
IEEE Transactions on Power Systems, 40(4), 3105-3116."

The algorithm has two steps: 1) solve relaxed problem and get many optimality cuts
2) consider the decomposed original problem, add optimality custs from step 1, and continue the BD. 
Note that optimality cuts from Step 1 do not eliminate any integer solutions

@author: Rahman Khorramfar
'''
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
import psutil, os;  # for memory usage

class BD():
    def __init__(self, data, Setting):
        self.data = data;
        self.Setting = Setting;
        self.MP_DV = DV_Classes.Power_System_Investment_Decision_Variables();
        self.MP_DV_values = DV_Classes.Power_System_Investment_Decision_Values();
        self.MP_model = [];
        self.best_MP_DV_vals = DV_Classes.Power_System_Investment_Decision_Values();  # record best inv decisions when updating the UB

        self.SP_DV = [DV_Classes.Power_System_Operational_Decision_Variables() for _ in range(self.data.num_rep_periods)];
        self.SP_Duals = [DV_Classes.Dual_vals(data) for _ in range(self.data.num_rep_periods)];
        self.SP_DV_values = [DV_Classes.Power_System_Operational_Decision_Values() for _ in range(self.data.num_rep_periods)];
        self.SP_Con = [DV_Classes.Oper_Constraints_Names(data) for _ in range(self.data.num_rep_periods)];
        self.Cuts = [];
        
        self.SP_model = [None for _ in range(self.data.num_rep_periods)];
        self.LB = 0;
        self.UB = 1e15;
    
    def run_Benders(self):
        start_time = time.time()
        is_MILP = self.Setting['relax_int_vars'];
        self.build_MP_model();
        
        self.MP_model.optimize();
        print(f'MP Objective value: {np.round(self.MP_model.get_model_attribute(poi.ModelAttribute.ObjectiveValue),2)}');
        Get_Vals.get_investment_variable_values(self.MP_model, self.MP_DV, self.MP_DV_values, self.data);
        step_RBD = 0;
        # main loop for Step 0
        for iter in range(100):
            self.Cuts.append([[] for _ in range(self.data.num_rep_periods)]);
            for sp in range(self.data.num_rep_periods):
                self.build_SP_model(self.MP_DV_values, sp);
                self.SP_model[sp].optimize();
                # print(self.SP_model[sp].get_model_attribute(poi.ModelAttribute.TerminationStatus));
                self.get_SP_DV_dual_vals(sp); # both dual and DV values
                print(f'SP {sp} Objective value: {np.round(self.SP_model[sp].get_model_attribute(poi.ModelAttribute.ObjectiveValue)/1e7,1)}e7, shedding: {round(self.SP_DV_values[sp].load_shedding_cost)}, fuel: {round(self.SP_DV_values[sp].gas_fuel_cost)}, VOM: {round(self.SP_DV_values[sp].VOM_cost)}');
                
                # print(f'load shedding values: {self.SP_DV_values[sp].load_shedding}');
                self.Cuts[iter][sp] = self.SP_Duals[sp]; # record the cuts
                self.add_optimality_cut_to_MP_model(sp);

            # update UB and the best inv decisions
            self.update_UB_and_best_investment_values();

            # set the objective (changes in the regulaized problem) and re-solve MP, get inv values
            Objective_Function.define_MP_objective(self.MP_model, self.MP_DV, self.data, self.Setting);
            self.MP_model.optimize();
            Get_Vals.get_investment_variable_values(self.MP_model, self.MP_DV, self.MP_DV_values, self.data);
            
            
            # update LB, calculate gap
            self.LB = self.MP_model.get_model_attribute(poi.ModelAttribute.ObjectiveValue);
            Gap = np.round((self.UB-self.LB)*100/self.UB,1);
            print(f'\t\t\t Iteration {iter}: LB={round(self.LB/1e7)}e7, UB={round(self.UB/1e7)}e7, Gap={Gap}%');
    
            if abs(self.UB-self.LB)/self.UB < self.Setting['solver_gap']: # if converged enough
                print('Convergence achieved!');
                self.print_best_feasible_solution(step_RBD, start_time, Gap, iter);
                break;
            else:
                # solve regulaized MP, get new inv values
                self.solve_regularized_MP();









    def print_best_feasible_solution(self, step_RBD, start_time, Gap, nIter):
        for sp in range(self.data.num_rep_periods):
            self.build_SP_model(self.best_MP_DV_vals, sp);
            self.SP_model[sp].optimize();
            self.get_SP_DV_dual_vals(sp); # both dual and DV values
        DVo_vals = DV_Classes.Power_System_Operational_Decision_Values();
        Get_Vals.concat_SP_models_values(self.SP_DV_values, DVo_vals, self.data, self.Setting);
        process = psutil.Process(os.getpid());
        memory_info = process.memory_info();
        RAM_MB = memory_info.rss / (1024 * 1024);
        Print_Outcomes.publish_summary(self.MP_DV_values, DVo_vals, step_RBD, nIter, self.LB, self.data, self.Setting, start_time, Gap, RAM_MB);
                

    def update_UB_and_best_investment_values(self):
        UB_temp = self.MP_DV_values.total_investment_cost;
        for sp in range(self.data.num_rep_periods):
            UB_temp += self.SP_DV_values[sp].operational_cost;
        if UB_temp < self.UB:
            self.UB = UB_temp;
            self.best_MP_DV_vals = self.MP_DV_values;
            self.print_sum_inv_variables(self.best_MP_DV_vals);


    def print_sum_inv_variables(self, MP_vals):
              # print some of the values
        for g in range(self.data.num_generators):
            for n in range(self.data.num_nodes):
                if MP_vals.gen_operational[g,n] > 0.5:
                    print(f'gen_op[{g},{n}] = {round(MP_vals.gen_operational[g,n])}');
        for s in range(self.data.num_storages):
            for n in range(self.data.num_nodes):
                if MP_vals.storage_level[s,n] > 0.5:
                    print(f'storage_level[{s},{n}] = {round(MP_vals.storage_level[s,n])}');
                if MP_vals.storage_capacity[s,n] >0.5:
                    print(f'storage_capacity[{s},{n}] = {round(MP_vals.storage_capacity[s,n])}');
        for l in range(self.data.num_lines):
            if MP_vals.line_established[l] > 0.5:
                print(f'line_established[{l}] = {round(MP_vals.line_established[l])}');
        print(f'total SP cost {sum(MP_vals.theta[i] for i in range(self.data.num_rep_periods))}');

        for d in range(self.data.num_rep_periods):
            if MP_vals.emissions_per_period[d] > 0:
                print(f'emissions_per_period[{d}] = {MP_vals.emissions_per_period[d]}');
        print(f'total inv cost: {MP_vals.total_investment_cost}');



    
    def solve_regularized_MP(self):
        alpha = 0.5;
        self.MP_model.set_objective(0, poi.ObjectiveSense.Minimize);
    
        # calculate LB_k
        LBk = self.LB + alpha*(self.UB - self.LB);
        reg_const = self.MP_model.add_linear_constraint(self.MP_DV.total_investment_cost + poi.quicksum(self.MP_DV.theta[s] for s in range(self.data.num_rep_periods)), poi.Leq, LBk);
        self.MP_model.optimize();
        print(f'\t\t\t\t LBk value: {round(LBk/1e7)}e7 \n');
        Get_Vals.get_investment_variable_values(self.MP_model, self.MP_DV, self.MP_DV_values, self.data);
    
        self.MP_model.delete_constraint(reg_const);




    def add_optimality_cut_to_MP_model(self, sp):
        # implement a function to add optimality cuts to the MP model based on the dual values obtained from the SP
        slice1 = np.arange(sp*self.Setting['hours_per_period'], (sp+1)*self.Setting['hours_per_period']);
        sp_hours = self.data.rep_hours[slice1];
        nT = len(sp_hours);
        
        lhs = poi.ExprBuilder();
        lhs += self.MP_DV.theta[sp];

        # terms from production limit and ramping constraints
        for g in range(self.data.num_generators):
            for n in range(self.data.num_nodes):
                for t in range(nT):
                    if self.data.Generators[g].is_thermal:
                        lhs -= self.SP_Duals[sp].prod_limit[g,n,t]*(self.data.Generators[g].nameplate_capacity*self.MP_DV.gen_operational[g,n]);
                    elif self.data.Generators[g].Type=='solar-UPV':
                        lhs -= self.SP_Duals[sp].prod_limit[g,n,t]*(self.data.Nodes[n].solar_cf[sp_hours[t]]*self.data.Generators[g].nameplate_capacity*self.MP_DV.gen_operational[g,n]);
                    elif self.data.Generators[g].Type=='wind-new':
                        lhs -= self.SP_Duals[sp].prod_limit[g,n,t]*(self.data.Nodes[n].wind_cf[sp_hours[t]]*self.data.Generators[g].nameplate_capacity*self.MP_DV.gen_operational[g,n]);

                    if t>0 and self.data.Generators[g].is_thermal:
                        lhs -= self.SP_Duals[sp].ramp_limit_up[g,n,t]*(self.data.Generators[g].ramp_rate*self.data.Generators[g].nameplate_capacity*self.MP_DV.gen_operational[g,n]);
                        lhs -= self.SP_Duals[sp].ramp_limit_down[g,n,t]*(self.data.Generators[g].ramp_rate*self.data.Generators[g].nameplate_capacity*self.MP_DV.gen_operational[g,n]);
        # Balance equation
        if self.Setting['is_copper_plate_approx']:
            for t in range(nT):
                rhs = 0;
                [rhs := rhs + self.data.Nodes[n].demand[sp_hours[t]] for n in range(self.data.num_nodes)];
                lhs -= self.SP_Duals[sp].load_balance[t]*rhs;
        else:
            for n in range(self.data.num_nodes):
                for t in range(nT):                                
                    lhs -= self.SP_Duals[sp].load_balance[n,t]*self.data.Nodes[n].demand[sp_hours[t]];

        # flow
        if not self.Setting['is_copper_plate_approx']:
            for l in range(self.data.num_lines):
                for t in range(nT):
                    lhs -= self.SP_Duals[sp].flow_limit1[l,t]*self.MP_DV.line_established[l];
                    lhs -= self.SP_Duals[sp].flow_limit2[l,t]*self.MP_DV.line_established[l];
        
        # storage
        for s in range(self.data.num_storages):                
            for n in range(self.data.num_nodes):
                lhs -= self.SP_Duals[sp].storage_SOC_balance[n]*(self.MP_DV.storage_level[s,n]/2);
                for t in range(nT):
                    lhs -= self.SP_Duals[sp].storage_charge_limit[n,t]*self.MP_DV.storage_capacity[s,n];
                    lhs -= self.SP_Duals[sp].storage_discharge_limit[n,t]*self.MP_DV.storage_capacity[s,n];
                    lhs -= self.SP_Duals[sp].storage_SOC_limit[n,t]*self.MP_DV.storage_level[s,n];    
        # emissions limit
        if self.Setting['Decarbonization_target'] > 0:
            lhs -= self.SP_Duals[sp].emissions_limit*self.MP_DV.emissions_per_period[sp];


        self.MP_model.add_linear_constraint(lhs, poi.Geq, 0);
        # Model.cb_add_lazy_constraint(lhs, poi.Geq, 0);



    def build_MP_model(self): 
        if self.Setting['solver']=='gurobi':
            self.MP_model = gurobi.Model();
            self.MP_model.set_raw_parameter('LogToConsole', self.Setting['show_log_info']);
            self.MP_model.set_raw_parameter('OutputFlag', self.Setting['show_log_info']);
            if self.Setting['Cross_over_status']==0:                
                # self.P_model.set_raw_parameter('Presolve', -1);
                # self.P_model.set_raw_parameter('CrossoverBasis', 0);
                self.MP_model.set_raw_parameter('Method', 2);
                self.MP_model.set_raw_parameter('Crossover', 0);
                # self.MP_model.set_raw_parameter('BarHomogeneous', 1);                 
        if self.Setting['solver'] == 'highs':
            self.MP_model = highs.Model();  
        # self.MP_model.set_raw_parameter('MIPGap', self.Setting['solver_gap']);
        # self.MP_model.set_raw_parameter('LogFile', 'log.txt');
        

        Define_DVs.define_investment_decision_variables(self.MP_model, self.MP_DV, self.data, self.Setting);
        Objective_Function.define_MP_objective(self.MP_model, self.MP_DV, self.data, self.Setting);
#         # add constraints to the MP model
        Constraints.inv_const_num_operational_generators(self.MP_model, self.MP_DV, self.data, self.Setting);
        Constraints.inv_const_land_availability_for_renewables(self.MP_model, self.MP_DV, self.data);
        Constraints.inv_const_CRM(self.MP_model, self.MP_DV, self.data, self.Setting);
        Constraints.inv_storage_duaration_range(self.MP_model, self.MP_DV, self.data);
        Constraints.inv_const_emissions_limit(self.MP_model, self.MP_DV, self.data, self.Setting); # over periods, not per time step

        # implement a function to add cuts
    
    def build_SP_model(self, MP_vals, sp):  # sp: the SP number (representative period number)
        slice1 = np.arange(sp*self.Setting['hours_per_period'], (sp+1)*self.Setting['hours_per_period']);
        sp_hours = self.data.rep_hours[slice1];
        sp_hours_weights = self.data.rep_hours_weights[slice1];
        nT = len(sp_hours);
        if self.Setting['solver']=='gurobi':
            self.SP_model[sp] = gurobi.Model();
            self.SP_model[sp].set_raw_parameter('LogToConsole', self.Setting['show_log_info']);
            self.SP_model[sp].set_raw_parameter('OutputFlag', self.Setting['show_log_info']);
            if self.Setting['Cross_over_status']==0:
                # self.P_model.set_raw_parameter('Presolve', -1);
                # self.P_model.set_raw_parameter('CrossoverBasis', 0);
                self.SP_model[sp].set_raw_parameter('Method', 2);
                self.SP_model[sp].set_raw_parameter('Crossover', 0);
                # self.SP_model[sp].set_raw_parameter('BarHomogeneous', 1);                 
        if self.Setting['solver'] == 'highs':
            self.SP_model[sp] = highs.Model();   
        # self.SP_model[sp].set_raw_parameter('MIPGap', self.Setting['solver_gap']);
        
        Define_DVs.define_operational_decision_variables(self.SP_model[sp], self.SP_DV[sp], nT, self.data);
        Objective_Function.define_operational_cost_expression(self.SP_model[sp], self.SP_DV[sp], sp_hours_weights, self.data, self.Setting);
        self.SP_model[sp].set_objective(self.SP_DV[sp].operational_cost, poi.ObjectiveSense.Minimize);

        Constraints.oper_const_production_limits(self.SP_model[sp], self.MP_DV, self.SP_DV[sp], self.SP_Con[sp], MP_vals, sp_hours, self.data, self.Setting);
        Constraints.oper_const_ramping(self.SP_model[sp], self.MP_DV, self.SP_DV[sp], MP_vals, self.SP_Con[sp], nT, self.data, self.Setting);          
        Constraints.oper_const_balance_equation(self.SP_model[sp], self.SP_DV[sp], self.SP_Con[sp], sp_hours, self.data, self.Setting);
        Constraints.oper_const_flow_limits(self.SP_model[sp], self.MP_DV, self.SP_DV[sp], MP_vals, self.SP_Con[sp], nT, self.data, self.Setting); 
        Constraints.oper_const_emissions_limit(self.SP_model[sp], self.MP_DV, self.SP_DV[sp], MP_vals, self.SP_Con[sp], [sp], sp_hours_weights, self.data, self.Setting); 
        Constraints.oper_const_storage(self.SP_model[sp], self.MP_DV, self.SP_DV[sp], MP_vals, self.SP_Con[sp], nT, self.data, self.Setting);


    def get_SP_DV_dual_vals(self, sp):
        slice1 = np.arange(sp*self.Setting['hours_per_period'], (sp+1)*self.Setting['hours_per_period']);
        sp_hours = self.data.rep_hours[slice1];
        sp_hours_weights = self.data.rep_hours_weights[slice1];
        nT = len(sp_hours);
        Get_Vals.get_operational_variable_values(self.SP_model[sp], self.SP_DV[sp], self.SP_DV_values[sp], nT, self.data);
        Get_Vals.get_operational_constraint_dual_values(self.SP_model[sp], self.SP_Con[sp], self.SP_Duals[sp], nT, self.data, self.Setting);









