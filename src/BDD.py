'''
Bismillah
May 27, 2026 at 1:09am, Cambridge home
Implementation of the BDD1 strengthened Benders cuts from:

Rahmaniani, R., Ahmed, S., Crainic, T. G., Gendreau, M., & Rei, W. (2020).
The Benders dual decomposition method. Operations Research, 68(3), 878-895.

BDD1 keeps the existing GTEP Benders loop, solves the classical LP
subproblem to obtain the Benders subgradient, then solves a local-copy
subproblem and adds the strengthened optimality cut.

@author: Rahman Khorramfar
'''
import copy
import numpy as np
import pyoptinterface as poi
from pyoptinterface import gurobi
from pyoptinterface import highs

import src.Benders as Classical_Benders
import src.Constraints as Constraints
import src.DV_Classes as DV_Classes
import src.Define_DVs as Define_DVs
import src.Get_Vals as Get_Vals
import src.Objective_Function as Objective_Function


class BDD1_Cut:
    def __init__(self, sp, duals, local_vals, strengthened_operational_cost, fallback=False):
        self.sp = sp
        self.duals = duals
        self.local_vals = local_vals
        self.strengthened_operational_cost = strengthened_operational_cost
        self.fallback = fallback


class BD(Classical_Benders.BD):
    def solve_SP_instance(self, sp):
        self.build_SP_model(self.MP_DV_values, sp)
        self.SP_model[sp].optimize()
        self.get_SP_DV_dual_vals(sp)

        try:
            cut = self.solve_strengthened_SP_instance(sp, self.SP_Duals[sp])
        except Exception as exc:
            if not self.Setting.get('BDD1_fallback_to_classical', True):
                raise
            if self.Setting.get('BDD1_show_strengthening_log', True):
                print(f'\t\t BDD1 fallback to classical cut for SP {sp}: {exc}')
            cut = BDD1_Cut(sp, self.SP_Duals[sp], None, None, fallback=True)
        return sp, cut

    def add_optimality_cut_to_MP_model(self, sp, Cut):
        if isinstance(Cut, BDD1_Cut) and not Cut.fallback:
            self.add_strengthened_optimality_cut_to_MP_model(sp, Cut)
        elif isinstance(Cut, BDD1_Cut):
            super().add_optimality_cut_to_MP_model(sp, Cut.duals)
        else:
            super().add_optimality_cut_to_MP_model(sp, Cut)

    def solve_strengthened_SP_instance(self, sp, Duals):
        model, local_DV, local_DVo, local_con, sp_hours, sp_hours_weights = self.build_strengthened_SP_model(sp, Duals)
        model.optimize()

        local_oper_vals = DV_Classes.Power_System_Operational_Decision_Values()
        local_inv_vals = DV_Classes.Power_System_Investment_Decision_Values()
        nT = len(sp_hours)
        Get_Vals.get_operational_variable_values(model, local_DVo, local_oper_vals, nT, self.data)
        self.get_local_copy_values(model, local_DV, local_inv_vals)

        if self.Setting.get('BDD1_show_strengthening_log', True):
            classical_obj = self.SP_DV_values[sp].operational_cost
            strengthened_rhs = local_oper_vals.operational_cost + self.dual_weighted_master_value(sp, Duals, self.MP_DV_values) - self.dual_weighted_master_value(sp, Duals, local_inv_vals)
            lift = strengthened_rhs - classical_obj
            print(f'\t\t BDD1 SP {sp}: classical={round(classical_obj, 2)}, strengthened_rhs={round(strengthened_rhs, 2)}, lift={round(lift, 2)}')

        return BDD1_Cut(sp, Duals, local_inv_vals, local_oper_vals.operational_cost)

    def build_strengthened_SP_model(self, sp, Duals):
        slice1 = np.arange(sp*self.Setting['hours_per_period'], (sp+1)*self.Setting['hours_per_period'])
        sp_hours = self.data.rep_hours[slice1]
        sp_hours_weights = self.data.rep_hours_weights[slice1]
        nT = len(sp_hours)

        model = self.create_solver_model()
        self.set_strengthened_solver_parameters(model)

        local_setting = copy.copy(self.Setting)
        local_setting['solution_method'] = 'extensive_form'
        local_setting['relax_int_vars'] = False

        local_DV = DV_Classes.Power_System_Investment_Decision_Variables()
        local_DVo = DV_Classes.Power_System_Operational_Decision_Variables()
        local_con = DV_Classes.Oper_Constraints_Names(self.data)

        Define_DVs.define_investment_decision_variables(model, local_DV, self.data, local_setting)
        Define_DVs.define_operational_decision_variables(model, local_DVo, nT, self.data)
        Objective_Function.define_operational_cost_expression(model, local_DVo, sp_hours_weights, self.data, self.Setting)

        Constraints.inv_const_num_operational_generators(model, local_DV, self.data, local_setting)
        Constraints.inv_const_land_availability_for_renewables(model, local_DV, self.data)
        Constraints.inv_const_CRM(model, local_DV, self.data, local_setting)
        Constraints.inv_storage_duaration_range(model, local_DV, self.data)
        Constraints.inv_const_emissions_limit(model, local_DV, self.data, local_setting)

        Constraints.oper_const_production_limits(model, local_DV, local_DVo, local_con, None, sp_hours, self.data, local_setting)
        Constraints.oper_const_ramping(model, local_DV, local_DVo, None, local_con, nT, self.data, local_setting)
        Constraints.oper_const_balance_equation(model, local_DVo, local_con, sp_hours, self.data, local_setting)
        Constraints.oper_const_flow_limits(model, local_DV, local_DVo, None, local_con, nT, self.data, local_setting)
        self.add_local_emissions_constraint(model, local_DV, local_DVo, sp, sp_hours_weights, local_con)
        Constraints.oper_const_storage(model, local_DV, local_DVo, None, local_con, nT, self.data, local_setting)

        model.set_objective(
            local_DVo.operational_cost - self.dual_weighted_master_expr(sp, Duals, local_DV),
            poi.ObjectiveSense.Minimize
        )
        return model, local_DV, local_DVo, local_con, sp_hours, sp_hours_weights

    def add_strengthened_optimality_cut_to_MP_model(self, sp, Cut):
        lhs = poi.ExprBuilder()
        lhs += self.MP_DV.theta[sp]
        lhs -= self.dual_weighted_master_expr(sp, Cut.duals, self.MP_DV)
        lhs += self.dual_weighted_master_value(sp, Cut.duals, Cut.local_vals)
        lhs -= Cut.strengthened_operational_cost
        self.MP_model.add_linear_constraint(lhs, poi.Geq, 0)

        if self.Setting.get('BDD1_show_strengthening_log', True):
            current_rhs = Cut.strengthened_operational_cost + self.dual_weighted_master_value(sp, Cut.duals, self.MP_DV_values) - self.dual_weighted_master_value(sp, Cut.duals, Cut.local_vals)
            classical_rhs = self.SP_DV_values[sp].operational_cost
            print(f'\t\t BDD1 cut check SP {sp}: rhs@current={round(current_rhs, 2)}, classical={round(classical_rhs, 2)}')

    def create_solver_model(self):
        if self.Setting['solver'] == 'gurobi':
            return gurobi.Model()
        if self.Setting['solver'] == 'highs':
            return highs.Model()
        raise ValueError(f"Unsupported solver for BDD1: {self.Setting['solver']}")

    def set_strengthened_solver_parameters(self, model):
        if self.Setting['solver'] == 'gurobi':
            model.set_raw_parameter('OutputFlag', self.Setting['show_log_info'])
            model.set_raw_parameter('LogToConsole', self.Setting['show_log_info'])
            model.set_raw_parameter('MIPGap', self.Setting.get('BDD1_sp_mip_gap', 0.005))
            model.set_raw_parameter('Timelimit', self.Setting['wall_clock_time_lim'])
        if self.Setting['solver'] == 'highs':
            pass

    def add_local_emissions_constraint(self, model, DVi, DVo, sp, hours_weights, Con):
        Con.emissions_limit = np.empty((1), dtype=object)
        if self.Setting['Decarbonization_target'] > 0:
            nT = len(hours_weights)
            Con.emissions_limit[0] = model.add_linear_constraint(
                poi.quicksum(
                    hours_weights[t] * DVo.generation[g, n, t] * self.data.Generators[g].heat_rate * self.data.Generators[g].emission_kg_per_MMBtu
                    for g in range(self.data.num_generators)
                    for n in range(self.data.num_nodes)
                    for t in range(nT)
                    if self.data.Generators[g].is_thermal
                ) - DVi.emissions_per_period[sp],
                poi.Leq,
                0
            )

    def get_local_copy_values(self, model, DV, DV_values):
        DV_values.gen_established = np.array([[max(0, model.get_value(DV.gen_established[g, n])) for n in range(self.data.num_nodes)] for g in range(self.data.num_generators)])
        DV_values.gen_operational = np.array([[max(0, model.get_value(DV.gen_operational[g, n])) for n in range(self.data.num_nodes)] for g in range(self.data.num_generators)])
        DV_values.storage_capacity = np.array([[max(0, model.get_value(DV.storage_capacity[s, n])) for n in range(self.data.num_nodes)] for s in range(self.data.num_storages)])
        DV_values.storage_level = np.array([[max(0, model.get_value(DV.storage_level[s, n])) for n in range(self.data.num_nodes)] for s in range(self.data.num_storages)])
        DV_values.line_established = np.array([max(0, model.get_value(DV.line_established[l])) for l in range(self.data.num_lines)])
        DV_values.emissions_per_period = np.array([max(0, model.get_value(DV.emissions_per_period[d])) for d in range(self.data.num_rep_periods)])

    def dual_weighted_master_expr(self, sp, Duals, DV):
        slice1 = np.arange(sp*self.Setting['hours_per_period'], (sp+1)*self.Setting['hours_per_period'])
        sp_hours = self.data.rep_hours[slice1]
        nT = len(sp_hours)

        expr = poi.ExprBuilder()
        for g in range(self.data.num_generators):
            for n in range(self.data.num_nodes):
                for t in range(nT):
                    if self.data.Generators[g].is_thermal:
                        expr += Duals.prod_limit[g, n, t] * self.data.Generators[g].nameplate_capacity * DV.gen_operational[g, n]
                    elif self.data.Generators[g].Type == 'solar-UPV':
                        expr += Duals.prod_limit[g, n, t] * self.data.Nodes[n].solar_cf[sp_hours[t]] * self.data.Generators[g].nameplate_capacity * DV.gen_operational[g, n]
                    elif self.data.Generators[g].Type == 'wind-new':
                        expr += Duals.prod_limit[g, n, t] * self.data.Nodes[n].wind_cf[sp_hours[t]] * self.data.Generators[g].nameplate_capacity * DV.gen_operational[g, n]

                    if t > 0 and self.data.Generators[g].is_thermal:
                        expr += Duals.ramp_limit_up[g, n, t] * self.data.Generators[g].ramp_rate * self.data.Generators[g].nameplate_capacity * DV.gen_operational[g, n]
                        expr += Duals.ramp_limit_down[g, n, t] * self.data.Generators[g].ramp_rate * self.data.Generators[g].nameplate_capacity * DV.gen_operational[g, n]

        if not self.Setting['is_copper_plate_approx']:
            for l in range(self.data.num_lines):
                for t in range(nT):
                    expr += Duals.flow_limit1[l, t] * DV.line_established[l]
                    expr += Duals.flow_limit2[l, t] * DV.line_established[l]

        for s in range(self.data.num_storages):
            for n in range(self.data.num_nodes):
                expr += Duals.storage_SOC_balance[n] * DV.storage_level[s, n] / 2
                for t in range(nT):
                    expr += Duals.storage_charge_limit[n, t] * DV.storage_capacity[s, n]
                    expr += Duals.storage_discharge_limit[n, t] * DV.storage_capacity[s, n]
                    expr += Duals.storage_SOC_limit[n, t] * DV.storage_level[s, n]

        if self.Setting['Decarbonization_target'] > 0:
            expr += Duals.emissions_limit * DV.emissions_per_period[sp]
        return expr

    def dual_weighted_master_value(self, sp, Duals, DV_values):
        slice1 = np.arange(sp*self.Setting['hours_per_period'], (sp+1)*self.Setting['hours_per_period'])
        sp_hours = self.data.rep_hours[slice1]
        nT = len(sp_hours)
        val = 0

        for g in range(self.data.num_generators):
            for n in range(self.data.num_nodes):
                for t in range(nT):
                    if self.data.Generators[g].is_thermal:
                        val += Duals.prod_limit[g, n, t] * self.data.Generators[g].nameplate_capacity * DV_values.gen_operational[g, n]
                    elif self.data.Generators[g].Type == 'solar-UPV':
                        val += Duals.prod_limit[g, n, t] * self.data.Nodes[n].solar_cf[sp_hours[t]] * self.data.Generators[g].nameplate_capacity * DV_values.gen_operational[g, n]
                    elif self.data.Generators[g].Type == 'wind-new':
                        val += Duals.prod_limit[g, n, t] * self.data.Nodes[n].wind_cf[sp_hours[t]] * self.data.Generators[g].nameplate_capacity * DV_values.gen_operational[g, n]

                    if t > 0 and self.data.Generators[g].is_thermal:
                        val += Duals.ramp_limit_up[g, n, t] * self.data.Generators[g].ramp_rate * self.data.Generators[g].nameplate_capacity * DV_values.gen_operational[g, n]
                        val += Duals.ramp_limit_down[g, n, t] * self.data.Generators[g].ramp_rate * self.data.Generators[g].nameplate_capacity * DV_values.gen_operational[g, n]

        if not self.Setting['is_copper_plate_approx']:
            for l in range(self.data.num_lines):
                for t in range(nT):
                    val += Duals.flow_limit1[l, t] * DV_values.line_established[l]
                    val += Duals.flow_limit2[l, t] * DV_values.line_established[l]

        for s in range(self.data.num_storages):
            for n in range(self.data.num_nodes):
                val += Duals.storage_SOC_balance[n] * DV_values.storage_level[s, n] / 2
                for t in range(nT):
                    val += Duals.storage_charge_limit[n, t] * DV_values.storage_capacity[s, n]
                    val += Duals.storage_discharge_limit[n, t] * DV_values.storage_capacity[s, n]
                    val += Duals.storage_SOC_limit[n, t] * DV_values.storage_level[s, n]

        if self.Setting['Decarbonization_target'] > 0:
            val += Duals.emissions_limit * DV_values.emissions_per_period[sp]
        return val
