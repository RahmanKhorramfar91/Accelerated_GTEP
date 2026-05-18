
# -*- coding: utf-8 -*-
"""
Bismillah
Created on Friday, 1 August 19:42 2025  

for now, the model is implemented for green frield only. 

@author: Rahman Khorramfar
"""
import pyoptinterface as poi;
import numpy as np;


class Power_System_Investment_Decision_Variables:
    def __init__(self):
        # set of investment decision variables
        self.gen_established = [];      # established unt/capacity per generator (at each node)
        self.gen_operational = [];      # operational unt/capacity per generator (at each node)
        self.storage_capacity = [];     # storage charging and discharging capacity per each storage type (at each node)
        self.storage_level = [];        # storage energy level per each storage type (at each node)
        self.line_established = [];     # established line capacity between two nodes
        self.RPS_contribution_per_period = [];      # renewable energy contribution to RPS per time period across the region
        self.emissions_per_period =[];   # CO2 emissions per time period across the region

        # cost components
        self.total_investment_cost = [];# total investment cost of the system
        self.gen_est_cost = [];         #  generation establishment cost
        self.line_est_cost = [];        # transmission line establishment cost
        self.storage_est_cost = [];     # storage establishment cost
        self.gen_FOM_cost = [];         # fixed operation and maintenance cost per generator
        self.line_FOM_cost = [];        # fixed operation and maintenance cost per line
        self.storage_FOM_cost = [];     # fixed operation and maintenance cost per storage

        # other decision variables
        self.total_CO2_emissions_kg = [];  # total CO2 emissions in kg

        # used in the Benders only
        self.MP_cost = [];
        self.theta = [];
        self.total_SP_cost = [];


class Power_System_Operational_Decision_Variables:
    def __init__(self):
        # set of operational decision variables
        self.generation = [];           # generation per generator per time period (at each node)
        self.load_shedding = [];        # load shedding per time period (at each node)
        self.storage_charge = [];       # storage charging amount per each storage type per each time period (at each node)
        self.storage_discharge = [];    # storage charging amount per each storage type per each time period (at each node)
        self.SOC = [];                  # state of charge per each storage type per each time period (at each node)
        self.flow = [];                 # electric power flow per line per time period (between two nodes)
        self.total_emissions = [];          # total CO2 emissions across the region
    
        # cost components
        self.operational_cost = [];        # total operational cost of the system
        self.VOM_cost = [];             # variable operation and maintenance cost
        self.load_shedding_cost = [];   # load shedding cost
        self.gas_fuel_cost = [];        # gas fuel cost



class Power_System_Investment_Decision_Values(Power_System_Investment_Decision_Variables):
    def __init__(self): super().__init__();    
class Power_System_Operational_Decision_Values(Power_System_Operational_Decision_Variables):
    def __init__(self): super().__init__(); 


class Oper_Constraints_Names:
    def __init__(self, data):
        self.prod_limit_thermal = [];
        self.prod_limit_solar = [];
        self.prod_limit_wind = [];
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
        self.line_expansion_limit = [];

class Dual_vals(Oper_Constraints_Names):
    def __init__(self, data=None): super().__init__(data);



