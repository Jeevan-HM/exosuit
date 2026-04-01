
if heel > threshold and m45 < threshold:# stance phase start
    gait='SF'
    gait_send=1
elif heel > threshold and m45 > threshold: # stance 
    gait='MST'
    gait_send=2
elif heel < threshold and m45 > threshold: # swing start
    gait='TST'
    gait_send=3
elif heel < threshold and m45 < threshold and m12 < threshold and toe < threshold: # swing start
    gait='SW'
    gait_send=4