'''
Bismillah
May 27, 2026 at 1:09am, Cambridge home
Paper-style implementation of the BDD1 strengthened Benders cuts from:

Rahmaniani, R., Ahmed, S., Crainic, T. G., Gendreau, M., & Rei, W. (2020).
The Benders dual decomposition method. Operations Research, 68(3), 878-895.

The implementation explicitly builds the local-copy subproblem with z = y*
linking constraints to obtain the equality multipliers, then relaxes/prices
those linking constraints to generate a strengthened Benders cut.

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
    def __init__(self, sp, multipliers, local_vals, operational_cost, fallback=False):
        self.sp = sp
        self.multipliers = multipliers
        self.local_vals = local_vals
        self.operational_cost = operational_cost
        self.fallback = fallback


class Investment_Copy_Multipliers:
    def __init__(self, data):
        self.gen_established = np.zeros((data.num_generators, data.num_nodes))
        self.gen_operational = np.zeros((data.num_generators, data.num_nodes))
        self.storage_capacity = np.zeros((data.num_storages, data.num_nodes))
        self.storage_level = np.zeros((data.num_storages, data.num_nodes))
        self.line_established = np.zeros(data.num_lines)
        self.emissions_per_period = np.zeros(data.num_rep_periods)


class Investment_Copy_Links:
    def __init__(self, data):
        self.gen_established = np.empty((data.num_generators, data.num_nodes), dtype=object)
        self.gen_operational = np.empty((data.num_generators, data.num_nodes), dtype=object)
        self.storage_capacity = np.empty((data.num_storages, data.num_nodes), dtype=object)
        self.storage_level = np.empty((data.num_storages, data.num_nodes), dtype=object)
        self.line_established = np.empty(data.num_lines, dtype=object)
        self.emissions_per_period = np.empty(data.num_rep_periods, dtype=object)


class BD(Classical_Benders.BD):
    def solve_SP_instance(self, sp):
        try:
            fixed_model, fixed_DV, fixed_DVo, fixed_links, sp_hours = self.build_fixed_copy_SP_model(sp)
            fixed_model.optimize()
            self.require_optimal_solution(fixed_model, f'fixed-copy SP {sp}')

            nT = len(sp_hours)
            Get_Vals.get_operational_variable_values(fixed_model, fixed_DVo, self.SP_DV_values[sp], nT, self.data)
            multipliers = self.get_copy_link_duals(fixed_model, fixed_links)
            cut = self.solve_strengthened_SP_instance(sp, multipliers)
        except Exception as exc:
            if not self.Setting.get('BDD1_fallback_to_classical', True):
                raise
            if self.Setting.get('BDD1_show_strengthening_log', True):
                print(f'\t\t BDD1 fallback to inherited classical cut for SP {sp}: {exc}')
            self.build_SP_model(self.MP_DV_values, sp)
            self.SP_model[sp].optimize()
            self.get_SP_DV_dual_vals(sp)
            return sp, self.SP_Duals[sp]

        return sp, cut

    def add_optimality_cut_to_MP_model(self, sp, Cut):
        if isinstance(Cut, BDD1_Cut):
            self.add_bdd1_cut_to_MP_model(sp, Cut)
        else:
            super().add_optimality_cut_to_MP_model(sp, Cut)

    def build_fixed_copy_SP_model(self, sp):
        model, local_DV, local_DVo, local_con, sp_hours, sp_hours_weights = self.build_local_copy_SP_model(sp, relax_copy_integrality=True)
        links = self.add_copy_link_constraints(model, local_DV)
        model.set_objective(local_DVo.operational_cost, poi.ObjectiveSense.Minimize)
        return model, local_DV, local_DVo, links, sp_hours

    def solve_strengthened_SP_instance(self, sp, multipliers):
        model, local_DV, local_DVo, local_con, sp_hours, sp_hours_weights = self.build_local_copy_SP_model(sp, relax_copy_integrality=False)
        model.set_objective(
            local_DVo.operational_cost - self.copy_multiplier_expr(multipliers, local_DV),
            poi.ObjectiveSense.Minimize
        )
        model.optimize()
        self.require_optimal_solution(model, f'strengthened SP {sp}')

        local_oper_vals = DV_Classes.Power_System_Operational_Decision_Values()
        local_inv_vals = DV_Classes.Power_System_Investment_Decision_Values()
        nT = len(sp_hours)
        Get_Vals.get_operational_variable_values(model, local_DVo, local_oper_vals, nT, self.data)
        self.get_local_copy_values(model, local_DV, local_inv_vals)

        fixed_obj = self.SP_DV_values[sp].operational_cost
        strengthened_rhs = local_oper_vals.operational_cost + self.copy_multiplier_value(multipliers, self.MP_DV_values) - self.copy_multiplier_value(multipliers, local_inv_vals)
        self.validate_strengthened_cut(sp, fixed_obj, strengthened_rhs)

        if self.Setting.get('BDD1_show_strengthening_log', True):
            lift = strengthened_rhs - fixed_obj
            print(f'\t\t BDD1 SP {sp}: fixed-copy={round(fixed_obj, 2)}, strengthened_rhs={round(strengthened_rhs, 2)}, lift={round(lift, 2)}')

        return BDD1_Cut(sp, multipliers, local_inv_vals, local_oper_vals.operational_cost)

    def require_optimal_solution(self, model, model_name):
        status = model.get_model_attribute(poi.ModelAttribute.TerminationStatus)
        if status != poi.TerminationStatusCode.OPTIMAL:
            raw_status = model.get_model_attribute(poi.ModelAttribute.RawStatusString)
            raise RuntimeError(f'{model_name} did not solve to optimality: {status} ({raw_status})')

    def validate_strengthened_cut(self, sp, fixed_obj, strengthened_rhs):
        if not np.isfinite(strengthened_rhs):
            raise RuntimeError(f'BDD1 strengthened cut for SP {sp} has non-finite RHS: {strengthened_rhs}')

        tolerance = self.Setting.get('BDD1_cut_validation_tol', 1e-6) * max(1.0, abs(fixed_obj))
        if strengthened_rhs < fixed_obj - tolerance:
            raise RuntimeError(
                f'BDD1 strengthened cut for SP {sp} is invalid at the current MP point: '
                f'rhs={strengthened_rhs}, fixed-copy={fixed_obj}'
            )

    def build_local_copy_SP_model(self, sp, relax_copy_integrality):
        slice1 = np.arange(sp*self.Setting['hours_per_period'], (sp+1)*self.Setting['hours_per_period'])
        sp_hours = self.data.rep_hours[slice1]
        sp_hours_weights = self.data.rep_hours_weights[slice1]
        nT = len(sp_hours)

        model = self.create_solver_model()
        self.set_strengthened_solver_parameters(model)

        local_setting = copy.copy(self.Setting)
        local_setting['solution_method'] = 'extensive_form'
        local_setting['relax_int_vars'] = relax_copy_integrality

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

        return model, local_DV, local_DVo, local_con, sp_hours, sp_hours_weights

    def add_copy_link_constraints(self, model, DV):
        links = Investment_Copy_Links(self.data)
        for g in range(self.data.num_generators):
            for n in range(self.data.num_nodes):
                links.gen_established[g, n] = model.add_linear_constraint(DV.gen_established[g, n], poi.Eq, self.MP_DV_values.gen_established[g, n])
                links.gen_operational[g, n] = model.add_linear_constraint(DV.gen_operational[g, n], poi.Eq, self.MP_DV_values.gen_operational[g, n])

        for s in range(self.data.num_storages):
            for n in range(self.data.num_nodes):
                links.storage_capacity[s, n] = model.add_linear_constraint(DV.storage_capacity[s, n], poi.Eq, self.MP_DV_values.storage_capacity[s, n])
                links.storage_level[s, n] = model.add_linear_constraint(DV.storage_level[s, n], poi.Eq, self.MP_DV_values.storage_level[s, n])

        for l in range(self.data.num_lines):
            links.line_established[l] = model.add_linear_constraint(DV.line_established[l], poi.Eq, self.MP_DV_values.line_established[l])

        for d in range(self.data.num_rep_periods):
            links.emissions_per_period[d] = model.add_linear_constraint(DV.emissions_per_period[d], poi.Eq, self.MP_DV_values.emissions_per_period[d])

        return links

    def get_copy_link_duals(self, model, links):
        multipliers = Investment_Copy_Multipliers(self.data)
        for g in range(self.data.num_generators):
            for n in range(self.data.num_nodes):
                multipliers.gen_established[g, n] = model.get_constraint_attribute(links.gen_established[g, n], poi.ConstraintAttribute.Dual)
                multipliers.gen_operational[g, n] = model.get_constraint_attribute(links.gen_operational[g, n], poi.ConstraintAttribute.Dual)

        for s in range(self.data.num_storages):
            for n in range(self.data.num_nodes):
                multipliers.storage_capacity[s, n] = model.get_constraint_attribute(links.storage_capacity[s, n], poi.ConstraintAttribute.Dual)
                multipliers.storage_level[s, n] = model.get_constraint_attribute(links.storage_level[s, n], poi.ConstraintAttribute.Dual)

        for l in range(self.data.num_lines):
            multipliers.line_established[l] = model.get_constraint_attribute(links.line_established[l], poi.ConstraintAttribute.Dual)

        for d in range(self.data.num_rep_periods):
            multipliers.emissions_per_period[d] = model.get_constraint_attribute(links.emissions_per_period[d], poi.ConstraintAttribute.Dual)

        return multipliers

    def add_bdd1_cut_to_MP_model(self, sp, Cut):
        lhs = poi.ExprBuilder()
        lhs += self.MP_DV.theta[sp]
        lhs -= self.copy_multiplier_expr(Cut.multipliers, self.MP_DV)
        lhs += self.copy_multiplier_value(Cut.multipliers, Cut.local_vals)
        lhs -= Cut.operational_cost
        self.MP_model.add_linear_constraint(lhs, poi.Geq, 0)

        if self.Setting.get('BDD1_show_strengthening_log', True):
            current_rhs = Cut.operational_cost + self.copy_multiplier_value(Cut.multipliers, self.MP_DV_values) - self.copy_multiplier_value(Cut.multipliers, Cut.local_vals)
            fixed_rhs = self.SP_DV_values[sp].operational_cost
            print(f'\t\t BDD1 cut check SP {sp}: rhs@current={round(current_rhs, 2)}, fixed-copy={round(fixed_rhs, 2)}')

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

    def copy_multiplier_expr(self, multipliers, DV):
        expr = poi.ExprBuilder()
        for g in range(self.data.num_generators):
            for n in range(self.data.num_nodes):
                expr += multipliers.gen_established[g, n] * DV.gen_established[g, n]
                expr += multipliers.gen_operational[g, n] * DV.gen_operational[g, n]

        for s in range(self.data.num_storages):
            for n in range(self.data.num_nodes):
                expr += multipliers.storage_capacity[s, n] * DV.storage_capacity[s, n]
                expr += multipliers.storage_level[s, n] * DV.storage_level[s, n]

        for l in range(self.data.num_lines):
            expr += multipliers.line_established[l] * DV.line_established[l]

        for d in range(self.data.num_rep_periods):
            expr += multipliers.emissions_per_period[d] * DV.emissions_per_period[d]

        return expr

    def copy_multiplier_value(self, multipliers, DV_values):
        val = 0
        for g in range(self.data.num_generators):
            for n in range(self.data.num_nodes):
                val += multipliers.gen_established[g, n] * DV_values.gen_established[g, n]
                val += multipliers.gen_operational[g, n] * DV_values.gen_operational[g, n]

        for s in range(self.data.num_storages):
            for n in range(self.data.num_nodes):
                val += multipliers.storage_capacity[s, n] * DV_values.storage_capacity[s, n]
                val += multipliers.storage_level[s, n] * DV_values.storage_level[s, n]

        for l in range(self.data.num_lines):
            val += multipliers.line_established[l] * DV_values.line_established[l]

        for d in range(self.data.num_rep_periods):
            val += multipliers.emissions_per_period[d] * DV_values.emissions_per_period[d]

        return val
