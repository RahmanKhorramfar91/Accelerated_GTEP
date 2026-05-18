# import pyoptinterface as poi
from pyoptinterface import highs # Or your choice of solver (gurobi, mosek, etc.)

# model = highs.Model()
# x = model.add_variable(lb=0, ub=10)
# y = model.add_variable(lb=0, ub=10)
# model.add_linear_constraint(x + y, poi.ConstraintSense.GreaterEqual, 5)

# # 1. Set the initial objective
# initial_obj = 2 * x + 3 * y
# model.set_objective(initial_obj, sense=poi.ObjectiveSense.Minimize)

# # 2. Change the objective function in an iteration loop
# for i in range(1, 5):
#     new_obj = (i * x) - y  # Define your new objective mathematically
    
#     # Update the objective function and solve
#     model.set_objective(new_obj, sense=poi.ObjectiveSense.Minimize)
#     model.optimize()
    
#     print(f"Iteration {i} - Objective Value: {model.get_value(new_obj)}")


import pyoptinterface as poi
# Make sure to import the specific solver you are using (e.g., highs, gurobi, copt)
# import pyoptinterface_highs as highs 

# 1. Initialize the model and solver backend
model = highs.Model()

# 2. Define the decision variables
x = model.add_variable(name="x", lb=0.0)
y = model.add_variable(name="y", lb=0.0)

# 3. Define static constraints
model.add_linear_constraint(x + y, poi.ConstraintSense.LessEqual, 10.0)
model.add_linear_constraint(2*x + y, poi.ConstraintSense.LessEqual, 15.0)

# 4. Iteration Loop: Modify and solve the objective iteratively
# Suppose we want to sweep through different weights for the objective: c1*x + c2*y
objective_weights = [(1.0, 2.0), (3.0, 1.0), (5.0, 5.0)]

for i, (c1, c2) in enumerate(objective_weights):
    print(f"--- Iteration {i+1}: Objective is {c1}*x + {c2}*y ---")
    
    # Define the new mathematical expression
    new_obj_expr = c1 * x + c2 * y
    
    # Overwrite the previous objective function
    model.set_objective(new_obj_expr, sense=poi.ObjectiveSense.Maximize)
    
    # Optimize the updated model
    model.optimize()
    
    # Retrieve and print the results
    # if model.get_model_attribute(poi.ModelAttribute.TerminationStatus) == poi.TerminationStatus.Optimal:
    obj_val = model.get_model_attribute(poi.ModelAttribute.ObjectiveValue)
    x_val = model.get_value(x)
    y_val = model.get_value(y)
    print(f"Status: Optimal | Obj Value: {obj_val:.2f} | x: {x_val:.2f}, y: {y_val:.2f}\n")
