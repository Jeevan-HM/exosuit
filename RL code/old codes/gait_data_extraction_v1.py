import numpy as np
import csv

#load data
data = np.loadtxt(r"C:\Users\jz5zh\Desktop\Experiment 01_25\controller_realtime_data\active_20psi.txt", dtype=float,delimiter=",")
print(data.shape[0],'total data length') #row number
print(data.shape[1],'total data column') #column number
# print(data[0][0]) row 0 column 0
# 0: time
# 1: mocap sync
# 2: grf_l
# 3: grf_r
# 4: knee angle L
# 5: knee angle R
# 6: Pressure commanded
# 7: Pressure measured
# 8: inflate command
# 9: stance L
# 10: stance R
# 11: kneeMax detected
# 12: First kneeMax detected for current gait

####preprocess data into gaits
Gait_data = []
Temp_data = []
for t in range(data.shape[0]):
    if t == 0 or (t != 0 and data[t-1][9] == 0.0 and data[t][9] == 1.0):
        print('begin gait detect',t)
        Temp_data.append(data[t])
    elif (data[t][9] == 0.0 and data[t+1][9] == 1.0) or t == (data.shape[0] - 1):
        print('end gait detect',t)
        Temp_data.append(data[t])
        Total_gait_t = Temp_data[-1][0] - Temp_data[0][0]
        print('total gait time',Total_gait_t)
        #extract feature in the gait
        STF_STE = 0
        SWF_SWE = 0
        flag_stf = 0
        flag_swf = 0
        #markers for stf to ste
        t1 = 0
        t2 = 0
        #markers for swf to swe
        t3 = 0
        t4 = 0
        #markers for control command for stf to ste
        t5 = 0
        t6 = 0
        #markers for control command for swf to swe
        t7 = 0
        t8 = 0
        
        
        for i in range(len(Temp_data)):
            #get stf to ste time
            if (Temp_data[i][9] == 1) and (Temp_data[i][10] == 0) and flag_stf == 0:
                t1 = i
                flag_stf = 1
            if ((Temp_data[i][9] != 1) or (Temp_data[i][10] != 0)) and flag_stf == 1:
                t2 = i
                flag_stf = 0
             
            #swf to swe time
            if Temp_data[i][9] == 0 and Temp_data[i][12] == 1 and flag_swf == 0:
                t3 = i
                flag_swf = 1
            
            if  flag_swf == 1:
                if i == (len(Temp_data) - 1):
                    t4 = i
                    flag_swf = 0
                elif ((Temp_data[i][4] < Temp_data[i-1][4]) and (Temp_data[i][4] < Temp_data[i+1][4])):
                    t4 = i
                    flag_swf = 0
                    
            if i != (len(Temp_data) - 1):
                
                if Temp_data[i-1][8] == 0 and Temp_data[i][8] == 1 and t5 == 0:
                    t5 = i
                elif Temp_data[i+1][8] == 0 and Temp_data[i][8] == 1 and t5 != 0 and t6 == 0:
                    t6 = i
#                 elif Temp_data[i-1][8] == 0 and Temp_data[i][8] == 1 and t5 != 0 and t6 != 0 and t7 == 0:
#                     t7 = i
#                 elif Temp_data[i+1][8] == 0 and Temp_data[i][8] == 1 and t5 != 0 and t6 != 0 and t7 != 0 and t8 == 0:
#                     t8 = i
                    
#             if i == (len(Temp_data) - 1):
#                 if t7 != 0 and t8 == 0:
#                     t8 = i
                 
                
        
                
        STF_STE = Temp_data[t2][0] - Temp_data[t1][0]
        SWF_SWE = Temp_data[t4][0] - Temp_data[t3][0]
        T_c1 = Temp_data[t6][0] - Temp_data[t5][0]
        if T_c1 < 0:
            T_c1 = 0
#         T_c2 = Temp_data[t8][0] - Temp_data[t7][0]
#         print(STF_STE,'time between stf and ste')
#         print(SWF_SWE,'time between swf and swe')
#         print(t6,Temp_data[t6][0])
#         print(t5,Temp_data[t5][0])
#         print(t8,Temp_data[t8][0])
#         print(t7,Temp_data[t7][0])
#         print(T_c1,'control 1')
#         print(T_c2,'control 2')


        #store gait data
        #Total gait time, period time stf to ste, control 1
        Gait_data.append((Total_gait_t, STF_STE,T_c1))
        
        Temp_data = []
    else:
        Temp_data.append(data[t])
        


filename = "gait_data%d.csv"%(1)
with open(filename, 'w') as csvfile: 
    # creating a csv writer object 
    csvwriter = csv.writer(csvfile,lineterminator = '\n') 


    # writing the data rows 
    csvwriter.writerows(Gait_data)        

    
    