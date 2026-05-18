"""
Bismillah
Created on Wed 30 July 19:21 2025
  
the power system component classes include: node, generator types, generators, lines, and storage.
@author: Rahman Khorramfar
"""

import numpy as np
import os;
import pandas as pd;

class Node:
    def __init__(self):
        self.node_num = int(); # node number
        self.demand = np.array([]); # demand 
        self.lat_lon = np.array([]); # longitude, latitude
        self.area_wind = float(); # area in km^2 for wind    
        self.area_solar = float(); # area in km^2 for solar
        # self.land_availability = float(); # land availability  (no longer needed in the new param format)
        self.solar_cf = np.array([]); # solar capacity factor
        self.wind_cf = np.array([]); # wind capacity factor

        self.arcs = np.array([]); # arcs to other nodes, arcs and arc_signs are populated in the Transmission_Line class
        self.arc_signs = np.array([]); # signs of the arcs, used in the balance equations
    def populate_node_data(self, Setting, Nodes):
        df_nodes = pd.read_csv(f'{os.getcwd()}/data_for_generators_lines_storages/Power_Nodes_{Setting["balancing_authority"]}_{Setting['network_size']}_nodes.csv');
        dy = Setting['in_sample_year'];

        # if Setting['balancing_authority']=='ISONE':
        df_eDem = pd.read_csv(f'{os.getcwd()}/ISONE_Demand_CF_{Setting["network_size"]}_node/{Setting["balancing_authority"]}_demand_{dy}.csv');
        df_solar = pd.read_csv(f'{os.getcwd()}/ISONE_Demand_CF_{Setting["network_size"]}_node/{Setting["balancing_authority"]}_solar_CF_{dy}.csv');
        df_wind = pd.read_csv(f'{os.getcwd()}/ISONE_Demand_CF_{Setting["network_size"]}_node/{Setting["balancing_authority"]}_wind_CF_{dy}.csv');

        for n in range(len(df_nodes)):
            en = Node();
            en.node_num = df_nodes['node_num'].iloc[n];
            en.lat_lon = np.array([df_nodes['Lat'].iloc[n], df_nodes['Lon'].iloc[n]]);
            en.area_wind = df_nodes['wind_area_km2'].iloc[n];
            en.area_solar = df_nodes['solar_area_km2'].iloc[n];
            # en.land_availability = df_nodes['availability_50'].iloc[n];
            en.demand = np.round(df_eDem.iloc[:, n+1], 2);

            # fill nan with 0 in solar and wind capacity factors
            df_solar = df_solar.fillna(0);
            df_wind = df_wind.fillna(0);
            en.solar_cf = np.round(df_solar.iloc[:, n+1], 2);
            en.wind_cf = np.round(df_wind.iloc[:, n+1], 2);
            Nodes.append(en);


class Generator_Type:

    def __init__(self): 
        self.Type = str(); # name of the generator type, e.g., solar, wind-offshore, gas, nuclear, hydro
        self.nameplate_capacity = float(); # nameplate capacity in MW
        self.allowed_to_establish = bool(); # whether the generator type is allowed to be established
        self.is_thermal = bool(); # whether the generator type is thermal (gas, nuclear, coal)
        self.is_existing = bool(); # whether the generator type exists in the system
        self.annualized_capex_per_unit = float(); # capital expenditure per unit generator 
        self.VOM_per_MWh = float(); # variable operation and maintenance cost per MWh
        self.FOM_per_MW = float(); # fixed operation and maintenance cost per MW
        self.min_output = float(); # minimum stable output in percentage
        self.ramp_rate = float(); # ramp rate in percentage
        # self.co2_capture_rate = float(); # CO2 capture rate (not used, subsumed in the emission_kg_per_MMBtu parameter)
        self.heat_rate = float(); # heat rate in MMBtu/MWh
        self.lifetime = int(); # lifetime in years
        self.power2area_density = float(); # power to area density in MW/km^2
        self.emission_kg_per_MMBtu = float(); # emission in kg/MWh, used for calculating CO2 emissions
    def populate_generator_type_data(self, Setting, Generators):
        df_gen = pd.read_csv(f'{os.getcwd()}/data_for_generators_lines_storages/generator_parameters.csv');
        for i in range(len(df_gen)):
            plt = Generator_Type();
            plt.Type = df_gen['Type'][i];
            plt.power2area_density = df_gen['Density(MW/km2)'].iloc[i];
            plt.is_thermal = int(df_gen['is_thermal'][i]);
            plt.allowed_to_establish = df_gen['allowed_to_establish'][i];            
            if plt.allowed_to_establish==0:continue;
            if plt.is_thermal and Setting['RPS']==1: continue;
            
            plt.nameplate_capacity = df_gen['Nameplate capacity (MW)'][i];
            plt.is_existing = df_gen['is existing'][i];            
            plt.VOM_per_MWh = df_gen['VOM ($/MWh)'][i];
            # plt.co2_capture_rate = df_gen['Carbon capture rate'][i];
            plt.emission_kg_per_MMBtu = df_gen['Emission rate (kg/MMBtu)'][i];
            plt.heat_rate = df_gen['Heat Rate  (MMBtu/MWh)'][i];
            plt.lifetime = df_gen['Lifetime (year)'][i];
            plt.min_output = df_gen['Minimum stable output (%)'][i];
            plt.FOM_per_MW = df_gen['FOM ($/kW-yr)'][i]*plt.nameplate_capacity*1000;
            plt.ramp_rate = df_gen['Hourly Ramp rate (%)'][i];
            s1 = (1/(1+Setting['WACC'])**plt.lifetime);
            s2 = (Setting['WACC']/(1-s1)); 
            plt.annualized_capex_per_unit = s2*df_gen['CAPEX($/kw) (2035)'][i]*plt.nameplate_capacity*1000;
            Generators.append(plt);

class Transmission_Line:
    def __init__(self):
        self.is_existing = bool(); # whether the line exists in the system
        self.num = int(); # line number
        self.from_node = int(); # from node number
        self.to_node = int(); # to node number
        self.length = float(); # length in km
        self.capacity = float(); # capacity in MW
        self.annualized_capex = float(); # annualized capital expenditure 
        self.FOM = float(); # fixed operation and maintenance cost per MW
        self.existing_cap = float();  # if existing line, the line capacity
    def populate_line_data(self, Setting, Nodes, Lines):
        df_br = pd.read_csv(f'{os.getcwd()}/data_for_generators_lines_storages/Transmission_Lines_{Setting["balancing_authority"]}_{Setting["network_size"]}_nodes.csv');
        df_br_par = pd.read_csv(f'{os.getcwd()}/data_for_generators_lines_storages/transmission_line_parameters.csv');
    
        arcs = [[] for x in range(len(Nodes))];
        arc_signs = [[] for x in range(len(Nodes))];
        
        for b in range(len(df_br)):
            br = Transmission_Line();
            br.is_existing = False;

            # if br.is_existing:
            #     br.existing_cap = df_br['maxFlow'][b];
            # else:
            br.existing_cap = 0;
            br.num = b;
            br.from_node = int(df_br['from_node'][b]);
            br.to_node = int(df_br['to_node'][b]);            
            arcs[br.from_node].append(b);
            arcs[br.to_node].append(b);
            if br.from_node>br.to_node:
                arc_signs[br.from_node].append(-1);
                arc_signs[br.to_node].append(1);
            else:
                arc_signs[br.from_node].append(1);
                arc_signs[br.to_node].append(-1);
            
            br.length = df_br['distance_mile'][b];
            br.capacity = df_br['capacity_MW'][b];
            s1 = (1/(1+Setting['WACC'])**df_br_par['trans_line_lifetime'].iloc[0]);
            est_coef = (Setting['WACC']/(1-s1));
            br.FOM = df_br_par['trans_line_FOM ($/MW/mile)'].iloc[0]; # $/MW/mile
            br.annualized_capex = est_coef*br.length*df_br_par['trans_line_inv_cost (&/MW/mile)'].iloc[0];
            
            Lines.append(br);


        # create arcs and arc_sign for each node to be used in the balance equations
        for n in range(len(arcs)):
            Nodes[n].arcs = np.array(arcs[n]);
            Nodes[n].arc_signs = np.array(arc_signs[n]);

class Storage:
    def __init__(self):
        self.Type = str(); # name of the storage type, e.g., Li-ion, metal-air
        self.annualized_energy_capex_per_MW = float(); # capital expenditure for energy storage in $/kWh   
        self.annualized_power_capex_per_MW = float(); # capital expenditure for power storage in $/kW
        self.charging_eff = float(); # charging efficiency
        self.discharging_eff = float(); # discharging efficiency
        self.self_discharge = float(); # self-discharge rate in %/day
        self.FOM_energy = float(); # energy fixed operation and maintenance cost in 
        self.FOM_power = float(); # power fixed operation and maintenance cost in $/kW-yr
        self.lifetime = int(); # lifetime in years
        self.duration_range = float(); # duration range in hours, e.g., 4, 24 ,168
    def populate_storage_data(self, Setting, Storages): 
        df_str = pd.read_csv(f'{os.getcwd()}/data_for_generators_lines_storages/storage_parameters.csv');
        for i in range(len(df_str)):
            st = Storage();
            st.Type = df_str['Storage technology'][i];
            st.charging_eff = df_str['charging efficiency'][i];
            st.discharging_eff = df_str['discharging efficiency'][i];
            st.FOM_energy = df_str['energy FOM'][i];
            st.FOM_power = df_str['power FOM'][i];
            st.lifetime = int(df_str['lifetime'][i]);
            st.self_discharge = df_str['self-discharge'][i];
            st.duration_range = df_str['duration_range(h)'][i];
            
            s1 = (1/(1+Setting['WACC'])**st.lifetime);
            s2 = (Setting['WACC']/(1-s1));
            st.annualized_energy_capex_per_MW = s2*df_str['energy capex'][i];
            st.annualized_power_capex_per_MW = s2*df_str['power capex'][i];

            Storages.append(st);


class Data(Node, Generator_Type, Transmission_Line, Storage):
    def __init__(self, Setting):
        Node.__init__(self);
        Generator_Type.__init__(self);
        Transmission_Line.__init__(self);
        Storage.__init__(self);
        
        self.Nodes = []; # list of nodes
        self.Generators = []; # list of generator types
        self.Lines = []; # list of transmission lines
        self.Storages = []; # list of storage types

        # populate for nodes, generator types, transmission lines, and storage
        self.populate_data(Setting);
        self.num_nodes = len(self.Nodes); # number of nodes
        self.num_generators = len(self.Generators); # number of generator types 
        self.num_lines = len(self.Lines); # number of transmission lines
        self.num_storages = len(self.Storages); # number of storage types

        self.rep_periods = np.array([]); # set of representative periods
        self.rep_hours = np.array([]); # set of representative hours   
        self.rep_period_weights = np.array([]); # weights for representative periods
        self.rep_hours_weights = np.array([]); # weights for representative hours
        
        self.rep_periods, self.rep_hours, self.rep_period_weights, self.rep_hours_weights = self.rep_periods_and_weights(Setting);

        self.num_rep_periods = Setting['num_rep_periods'];
        self.num_rep_hours = self.num_rep_periods * Setting['hours_per_period']; # number of representative hours
        if Setting['balancing_authority']=='ISONE':
            self.total_emissions = Setting['ISONE_power_emission_1990']; # total emissions in 1990 for the balancing authority, used for calculating emission reduction percentage
        # if not Setting['solution_method']=='extensive_form':
        #     self.num_SPs = int(np.ceil(Setting['num_rep_days']/Setting['num_days_per_scenario']));
        #     self.scen_days = [];
        #     self.scen_hours = [];
        #     self.scen_day_weights = [];
        #     self.scen_hours_weights = [];
        #     self.scen_days, self.scen_hours, self.scen_day_weights, self.scen_hours_weights = self.get_scenario_days_and_weights(Setting);
    


    def populate_data(self, Setting):
        """
        this function populates the data for nodes, generator types, transmission lines, and storage.
        It reads the data from the csv files and populates the respective classes.
        """
        self.populate_node_data(Setting, self.Nodes);
        self.populate_generator_type_data(Setting, self.Generators);
        self.populate_line_data(Setting, self.Nodes, self.Lines);
        self.populate_storage_data(Setting, self.Storages);



    def rep_periods_and_weights(self, Setting):
        """ 
        this function reads the representative periods and weights from the csv files for the balancing authority.
        It returns the representative periods, hours, and their weights.
        """
        dy = Setting['in_sample_year'];
        df = pd.read_csv(f'{os.getcwd()}/Rep_periods/{Setting["balancing_authority"]}_{dy}_nPeriods={Setting["num_rep_periods"]}_nHours={Setting["hours_per_period"]}.csv');

        rep_periods = np.zeros(Setting['num_rep_periods'], dtype=int);
        rep_hours = np.zeros(Setting['num_rep_periods']*Setting['hours_per_period'], dtype=int);
        rep_period_weights = np.zeros(Setting['num_rep_periods'], dtype=int);
        rep_hours_weights = np.zeros(Setting['num_rep_periods']*Setting['hours_per_period'], dtype=int);

        s1 = df[df['is_medoid?']==1];
        s2 = s1.sort_values(['Cluster']);
        s1 = np.array(s2.index);
        rep_periods = sorted(s1);  # zero indexing
        for i in range(Setting['num_rep_periods']):
            s1 = np.array(df['Cluster']);
            i2 = df['Cluster'].iloc[rep_periods[i]];
            s2 = np.where(s1==i2);
            rep_period_weights[i] = len(s2[0]);
            rep_hours_weights[i*Setting['hours_per_period']:(i+1)*Setting['hours_per_period']] += rep_period_weights[i];
            for j in range(Setting['hours_per_period']):
                rep_hours[i*Setting['hours_per_period']+j] = rep_periods[i]*Setting['hours_per_period']+j;
        
        return rep_periods, rep_hours, rep_period_weights, rep_hours_weights;


    # def get_scenario_days_and_weights(self, Setting):
    #     """
    #     this function   does this  

    #     """
    #     nS = self.num_scenarios;
    #     scen_days = [[] for _ in range(nS)];
    #     scen_hours = [[] for _ in range(nS)];
    #     scen_day_weights = [[] for _ in range(nS)];
    #     scen_hours_weights = [[] for _ in range(nS)];

    #     for s in range(nS):
    #         if s==nS-1:
    #             scen_days[s] = self.rep_days[s*Setting['num_days_per_scenario']:];
    #             scen_hours[s] = self.rep_hours[s*Setting['num_days_per_scenario']*24:];
    #             scen_day_weights[s] = self.rep_day_weights[s*Setting['num_days_per_scenario']:];
    #             scen_hours_weights[s] = self.rep_hours_weights[s*Setting['num_days_per_scenario']*24:];
                
    #         else:
    #             scen_days[s] = self.rep_days[s*Setting['num_days_per_scenario']:Setting['num_days_per_scenario']*(s+1)];
    #             scen_hours[s] = self.rep_hours[s*Setting['num_days_per_scenario']*24:Setting['num_days_per_scenario']*24*(s+1)];
    #             scen_day_weights[s] = self.rep_day_weights[s*Setting['num_days_per_scenario']:Setting['num_days_per_scenario']*(s+1)];
    #             scen_hours_weights[s] = self.rep_hours_weights[s*Setting['num_days_per_scenario']*24:Setting['num_days_per_scenario']*24*(s+1)];

    #     # normalize weights so they add up to almost the weight of a full-year. The normalization is important to get a realistic cost estimate per scenario
    #     for scen in range(nS):
    #         scen_day_weights[scen] = np.round(scen_day_weights[scen]*(365/np.sum(scen_day_weights[scen])));
    #         scen_hours_weights[scen] = np.round(scen_hours_weights[scen]*(365*24/np.sum(scen_hours_weights[scen])));


    #     return scen_days, scen_hours, scen_day_weights, scen_hours_weights;





