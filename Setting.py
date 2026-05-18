# -*- coding: utf-8 -*-
"""
Bismillah
Created on Wed 30 July 19:16 2025
@author: Rahman Khorramfar
"""

# Setting is a dictionary containing the main parameters and settings for the problem. The given values are default. 

Setting = {
    'balancing_authority': 'ISONE',      # balancing authority (e.g., 'ERCOT', 'ISONE')
    'network_size': 6,                   # network size (here, 6, 17, 64)    
    'in_sample_year': 2005,              # in-sample year
    # 'data_year': ,                   # (not needed, if in-sample, the data_year becomes in-sample year, otherwise, out-of-sample year)
    'num_rep_periods': 2,                   # number of representative periods (e.g., day or week) 
    'hours_per_period': 24,        # number of hours in each representative period (e.g., 24 for day, 168 for week)
    'RPS': 0.9,                            # renewable portfolio standard
    'CRM_reserve': 0.0,                  # capacity reserve margin [fraction]    
    'is_green_field': True,              # whether the problem is green field (1) or brown field (0)
    'expansion_allowed': True,           # whether gen/line expansion is allowed
    'is_copper_plate_approx': False,         # whether to use copper plate model (no transmission lines)
    'UC_active': True,                  # whether unit commitment is active
    'relax_int_vars': False,                 # whether to relax integer variables in the optimization   
    'relax_UC_vars': True,               # whether to relax unit commitment variables
    'load_shedding_penalty': 10000,      # penalty for load shedding
    'WACC': 0.062,                       # weighted average cost of capital
    'NG_price': 2.5,                     # natural gas price in $/MMBtu, in 2024
    'ISONE_power_emission_1990': 4.39e7,      # New England power sector emission in 1990 (ton CO2)
    'Decarbonization_target': 0.8,              # decarbonization target (e.g., 0.8 for 80% reduction by 2050)
    # solution method
    'solution_method': 'extensive_form',

    # result publication setting
    'print_result_header': False,            # whether to print the result header in the output summary file
    'print_extensive_outcome': False,        # whether to print all variables in a separate file

    # solver setting
    'solver': 'gurobi',                  # solver name (gurobi, highs)
    'wall_clock_time_lim': 1 * 3600,    # time limit for the solver in seconds
    'solver_gap': 0.01,                  # solver gap
    'solver_thread_num': 6,              # number of thread solver uses
    'show_log_info': False,                  # whether to show log information
    'print_log_output': False,               # whether to print log output in log.txt
    'Cross_over_status': False,              # cross over parameter status (1: on, 0:off)

}
