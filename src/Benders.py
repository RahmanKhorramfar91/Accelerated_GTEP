'''
Bismillah
May 18, 2026 at 19:37, Cambriedge home
implmentation of Regularized Benders from:


"Pecci, F., & Jenkins, J. D. (2025). 
Regularized benders decomposition for high performance capacity expansion models. 
IEEE Transactions on Power Systems, 40(4), 3105-3116."

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

class BD():
    def __init__(self, data, Setting):
        self.data = data;
        self.Setting = Setting;
        self.MP_DV = DV_Classes.Power_System_Investment_Decision_Values();
        self.SP_DV = DV_Classes.Power_System_Operational_Decision_Values();
        self.SP_Duals = DV_Classes.Dual_vals(data);
        self.MP_DV_values = DV_Classes.Power_System_Investment_Decision_Values();
        self.SP_DV_values = DV_Classes.Power_System_Operational_Decision_Values();
        self.SP_Con = DV_Classes.Oper_Constraints_Names(data);
        
        self.LB = 0;
        self.UB = np.inf;




