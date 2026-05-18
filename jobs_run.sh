#!/bin/bash                                                                                                                                                              
#SBATCH -n 64 # number of cores                                                                                                                                          
#SBATCH -N 1 # number of nodes                                                                                                                                           
#SBATCH -t 0-72:00 # runtime limit                                                                                                                                       
#SBATCH -p sched_mit_mhowland_r8 # run on this partition                                                                                                                 
#SBATCH -o log_%j.txt #print log output with job_id suffix                                                                                                              
#SBATCH -e error_log.txt # print error log                                                                                                                                 
#SBATCH --mem 180GB                                                                                                                                                        
#SBATCH --mail-type=BEGIN,END # mail when job starts and ends                                                                                                            
#SBATCH --mail-user=khorram@mit.edu #email recipient                                                                                                                     

python Main.py
