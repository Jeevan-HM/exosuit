%% Load and Plot Output data from controller algorithm
clc; clear;

%% Options

Compute_Joint_Angles_From_Quaternion = 0;
Plot_GaitEvents_in_JointAngles = 0;

%% Load Data

dataIMU = importdata('data_6.txt');

time = dataIMU(:,1);
knee_angle = dataIMU(:,2); %[deg]
hip_angle = dataIMU(:,3); %[deg]
knee_vel = dataIMU(:,4); %[deg/s]
hip_vel = dataIMU(:,5); %[deg/s]
thigh_vel = dataIMU(:,6); %[rad/s]
thigh_vel = -thigh_vel*(180/pi); %[deg/s] Flip Sign, and convert units

% %Gait Events:
% A = dataIMU(:,7);
% B = dataIMU(:,8);
% C = dataIMU(:,9);
% D = dataIMU(:,10);
% E = dataIMU(:,11);

%Quaternion Data that was used for real-time angle computation
QuatShank = dataIMU(:,12:15);
QuatThigh = dataIMU(:,16:19);
QuatTorso = dataIMU(:,20:23);

%Thigh Phase Angle
[~, thigh_angle, ~] = Quat2Euler(QuatThigh);
thigh_angle = -thigh_angle; %note, negative simbol so that extension is positive (originally flexion is positive).


hip_angle = thigh_angle; disp('NOTE: Hip Angle data is replaced by Thigh Angle data')
hip_vel = thigh_vel; disp('NOTE: Hip Velocity data is replaced by Gyroscope data')

% %Filter Knee Velocity:
% raw_knee_vel = knee_vel;
% [b,a] = butter(3,0.3);
% knee_vel = filter(b,a,knee_vel);
% disp('NOTE: FILTERING Knee Velocity Data with Butterworth Filter')


%% Debug Issues with Controller Algorithm

%Find Sampling Rate
time_between_samples = mean(diff(time))
sampling_frequency = 1/time_between_samples


ind_inc = 2000:3000;
% firstA = (diff(A) == 1); %Find first index that detects A
% firstB = (diff(B) == 1); %Find first index that detects B
% firstC = (diff(C) == 1); %Find first index that detects C
% firstD = (diff(D) == 1); %Find first index that detects D
% firstE = (diff(E) == 1); %Find first index that detects E


% plot(hip_angle(ind_inc), knee_angle(ind_inc))
% plot(time(ind_inc), knee_angle(ind_inc))
% 
% figure(1); clf; hold on
% plot(time,knee_angle)
% plot(time,E*50)
% % plot(time,knee_vel,'.-','MarkerSize',30)
% % xlim([30 36]+10)
% % ylim([-30 80])


% %Phase Plot with gait detection from controller
% figure(2); clf; hold on
% title('Phase Plot')
% 
% plot(hip_angle, knee_angle)
% % plot(-ThighAngle, knee_angle)
% 
% plot(hip_angle(firstA), knee_angle(firstA), '*')
% plot(hip_angle(firstB), knee_angle(firstB), '*')
% plot(hip_angle(firstC), knee_angle(firstC), '*')
% plot(hip_angle(firstD), knee_angle(firstD), '*')
% plot(hip_angle(firstE), knee_angle(firstE), '*')
% % plot(hip_angle(firstE), knee_angle(firstE), '*')
% 
% yline(0); xline(0)
% legend Data A B C D E
% Add_Labels()



% %Plot Knee Joint Angle
% figure(3); clf; hold on
% title('Knee Joint Angle')
% 
% plot(time,knee_angle)
% plot(time(firstA), knee_angle(firstA), '*')
% plot(time(firstB), knee_angle(firstB), '*')
% plot(time(firstC), knee_angle(firstC), '*')
% plot(time(firstD), knee_angle(firstD), '*')
% plot(time(firstE), knee_angle(firstE), '*')
% 
% plot(time,knee_vel,'.-', 'MarkerSize',20)
% %plot(time,knee_vel_filt,'.-', 'MarkerSize',20)
% 
% 
% yline(0)
% legend Data A B C D E Velocity Velocity-Filtered



%% Gait Events Detect in Matlab (Post-processing)

interval = 1:length(dataIMU); % 1200:1800 ;

% interval = interval + 300;

% %Plot All Joint Data
% figure(2343); clf; hold on
% % subplot(1,2,1); hold on
% plot(interval, knee_angle(interval))
% plot(interval, hip_angle(interval))
% plot(interval, knee_vel(interval)/10)
% plot(interval, hip_vel(interval)/10)
% legend 'Knee Angle' 'Hip Angle' 'Knee Vel/10' 'Hip Vel'
% grid on




% % % Gait Event Detection % % %

%Threshold for Gait Detect Events
tresh_E = 30;
tresh_A = 10;
tresh_C = 1;
tresh_D = 1;

%Point E: Detect Maximum Knee Flexion
logic_E = (abs(knee_vel) <= tresh_E) & (hip_vel < 0) & (knee_angle > 20);

%Point A: 
% logic_A = (abs(knee_vel) <= tresh_A) & (hip_vel > 0);
% logic_A = (abs(hip_vel) <= tresh_A) & (knee_vel < 0) & (hip_angle < -10);
logic_A = (-10 < hip_vel) & (hip_vel < 1) & (knee_vel < 0)  & (hip_angle < -10);
% logic_A = (abs(hip_vel) <= 30) & (abs(hip_vel) <= 10) & (hip_vel > 0)

%Point C: 
logic_C = (abs(hip_angle) <= tresh_C) & (hip_vel > 0);

%Point D:
% logic_D = (abs(knee_vel) <= tresh_D) & (hip_vel > 0);
% logic_D = (abs(knee_vel) <= 10) & (abs(hip_vel) <= 10) & (hip_angle > 1) ;
logic_D = (-10 < knee_vel) & (knee_vel < 10) & (hip_angle > 2);
% logic_D = (-5 < knee_vel) & (knee_vel < 5) & (knee_angle < 10) & (hip_vel < 30);


%Point B:
% logic_B = (abs(knee_vel) <= 5) & (hip_vel > 0) & (hip_angle < -5);
logic_B = (0 < knee_vel) & (knee_vel < 5) & (hip_vel > 0) & (hip_angle < -5);


%Store only 1st values, using "for loop" similar to Python implementation in real-time
NoSamples = 20; %Number of samples to collect for the vector check for 1st event detection
vectE = zeros(1,NoSamples);
FlagFirst = 0; FlagA = 0; FlagB = 0; FlagC = 0; FlagD = 0;
for i = 1:length(dataIMU)
    
    if i <= NoSamples %take 20 samples first
        vectE(i) = logic_E(i);
        E(i) = 0;
    else
        
        %Detect only first E event and store into variable
        vectE(1) = []; %delete first value
        vectE(end+1) = logic_E(i);  %add current value to last index of vectorE
        if (sum(vectE) == 1)  &&  (FlagFirst == 0)
            E(i) = 1;
            FlagFirst = 1;
            FlagA = 0; FlagB = 0; FlagC = 0; FlagD = 0;
        elseif (sum(vectE) == 0)
            FlagFirst = 0;

        else
            E(i) = 0;
        end
        
        
        %Detect First Events only of A,B,C,D
        if (logic_A(i) == 1)  &&  (FlagA == 0)
            A(i) = 1;
            FlagA = 1;
        else
            A(i) = 0;
        end
        
        if (logic_B(i) == 1)  &&  (FlagB == 0)
            B(i) = 1;
            FlagB = 1;
        else
            B(i) = 0;
        end
        
        if (logic_C(i) == 1)  &&  (FlagC == 0)
            C(i) = 1;
            FlagC = 1;
        else
            C(i) = 0;
        end
        
        if (logic_D(i) == 1)  &&  (FlagD == 0)
            D(i) = 1;
            FlagD = 1;
        else
            D(i) = 0;
        end
            
        
    end
end
        

%% PLOT RESULTS (Verify Gait Detection)

% %Verify First Values only:
% figure(111); clf; hold on
% plot(logic_C)
% plot(C, '--')
% legend 'E All' 'E First'


%Substitue for First Values Only
disp('NOTE: Substituting for Detection of First Even Only')
logic_A = logical(A);
logic_B = logical(B);
logic_C = logical(C);
logic_D = logical(D);
logic_E = logical(E);




% Plot PHASE PLOT with Gait Detection

figure(570); clf; hold on
subplot(1,2,1); hold on
title('Phase Plot, 0.5 m/s')

plot(hip_angle, knee_angle)
% plot(-ThighAngle, knee_angle)

plot(hip_angle(logic_E), knee_angle(logic_E), '*')
plot(hip_angle(logic_C), knee_angle(logic_C), '*')
plot(hip_angle(logic_A), knee_angle(logic_A), '*')
plot(hip_angle(logic_B), knee_angle(logic_B), '*')
plot(hip_angle(logic_D), knee_angle(logic_D), '*')

yline(0); xline(0)
legend 'IMU Data' E C A B D
Add_Labels()


% Plot JOINT ANGLES PLOT with Gait Detection

subplot(1,2,2); hold on
title('Knee Angle, 0.3 m/s')
plot(time, knee_angle, '.-')
plot(time(logic_E), knee_angle(logic_E), '*')
plot(time(logic_C), knee_angle(logic_C), '*')
plot(time(logic_A), knee_angle(logic_A), '*')
plot(time(logic_B), knee_angle(logic_B), '*')
plot(time(logic_D), knee_angle(logic_D), '*')
yline(0)
legend 'IMU Data' E C A B D
Add_Labels()
xlabel('Time (sec)')





%% Plot Gait Detection Events in Joint Angle Plots
if Plot_GaitEvents_in_JointAngles
    figure(6666); clf; hold on
    subplot(1,2,1); hold on
    title('Hip Angle, 0.3 m/s')
    plot(time, hip_angle, '.-')
    plot(time(logic_E), hip_angle(logic_E), '*')
    plot(time(logic_C), hip_angle(logic_C), '*')
    plot(time(logic_A), hip_angle(logic_A), '*')
    plot(time(logic_B), hip_angle(logic_B), '*')
    plot(time(logic_D), hip_angle(logic_D), '*')
    yline(0)
    legend 'IMU Data' E C A B D
    %Axis Label Direction of flexion/extension
    label_direction_hip = '\leftarrow Flexion                                                      Extension \rightarrow';
    ylabel({'Hip Angle', label_direction_hip})
    xlabel('Time (sec)')
    xlim([77.8 90.8])
    
    
    subplot(1,2,2); hold on
    title('Knee Angle, 0.3 m/s')
    plot(time, knee_angle, '.-')
    plot(time(logic_E), knee_angle(logic_E), '*')
    plot(time(logic_C), knee_angle(logic_C), '*')
    plot(time(logic_A), knee_angle(logic_A), '*')
    plot(time(logic_B), knee_angle(logic_B), '*')
    plot(time(logic_D), knee_angle(logic_D), '*')
    yline(0)
    legend 'IMU Data' E C A B D
    Add_Labels()
    xlabel('Time (sec)')
    xlim([77.5  88.3])
end

%% Hip Angle Velocity vs Gyro Data

% figure(99399); clf; hold on
% plot(hip_vel)
% plot(thigh_vel)
% legend Quaternion Gyro
% title('Hip Velocity')


%% Hip Angle Vs Thigh Angle Data Comparison

% 
% %Time Plot
% figure(3412346); clf; hold on
% plot(hip_angle)
% plot(ThighAngle)
% 
% Add_Labels(); grid on;
% xlabel('Time [sec]')

% return


% %Phase Plot
% figure(134512); clf; hold on
% subplot(1,2,1); hold on
% plot(hip_angle, knee_angle)
% title('Using Hip Angle')
% Add_Labels(); grid on;
% 
% subplot(1,2,2); hold on
% plot(ThighAngle, knee_angle)
% title('Using Thigh Angle')
% Add_Labels(); grid on;





%% Filter Knee Angle

% [b,a] = butter(3,0.2)
% filt_knee_angle = filter(b,a,knee_angle)
% 
% 
% figure(99999); clf; hold on
% subplot(1,2,1); hold on
% plot(hip_angle, filt_knee_angle)
% title('Using Hip Angle')
% Add_Labels(); grid on;
% 
% subplot(1,2,2); hold on
% plot(thigh_angle, filt_knee_angle)
% title('Using Thigh Angle')
% Add_Labels(); grid on;




%% Filter Knee Velocity

% %Filter Velocity
% % knee_vel_filt = knee_vel(1:end-1).* exp(-0.9*diff(time))
% 
% [b,a] = butter(3,0.2)
% knee_vel_filt = filter(b,a,knee_vel)
% 
% 
% figure(10); clf; hold on
% title('Velocity Filtering')
% plot(time,knee_vel,'.-', 'MarkerSize',20)
% plot(time,knee_vel_filt, 'MarkerSize',20)
% legend 'Velocity Raw' 'Velocity Filtered'



%% Compute Joint Angles From Quaternions (Matlab method comparison)
if Compute_Joint_Angles_From_Quaternion
    
    %Create Quaternion Object
    QuatShank = quaternion( QuatShank );
    QuatThigh = quaternion( QuatThigh );
    QuatTorso = quaternion( QuatTorso );
    
    %Compute Quaternion Difference
    for i = 1:length(dataIMU)
        QuatKnee(i) = conj(QuatShank(i))*QuatThigh(i);
        QuatHip(i) = conj(QuatTorso(i))*QuatThigh(i);
    end
   
    QuatKneeMat = QuatKnee.compact;
    QuatHipMat = QuatHip.compact;
    
    
    % Convert to Euler Angles
    
    %Knee
    [rollKneeQuat, pitchKneeQuat, yawKneeQuat] = Quat2Euler( QuatKneeMat );
    AngleKnee_Matlab = pitchKneeQuat;
    
    %Hip
    [rollHipQuat, pitchHipQuat, yawHipQuat] = Quat2Euler( QuatHipMat );
    AngleHip_Matlab = -pitchHipQuat;
    
    % Plot Angle Comparison    
    figure(2); clf; hold on
    plot(knee_angle)
    plot(AngleKnee_Matlab,'--')
    yline(0)
    legend 'Real-Time Computation (Python)' 'Post-Process Computation (Matlab)'
    
end


%% Subfunctions

function [roll,pitch,yaw] = Quat2Euler( Quaternion_Matrix )

q0 = Quaternion_Matrix(:,1);
q1 = Quaternion_Matrix(:,2);
q2 = Quaternion_Matrix(:,3);
q3 = Quaternion_Matrix(:,4);


roll  = atan2d(2*(q0.*q1+q2.*q3),  1-2*(q1.*q1 + q2.*q2));

pitch = asind(2*(q0.*q2-q3.*q1));

yaw = atan2d(2*(q0.*q3+q1.*q2),  1-2*(q2.*q2 + q3.*q3));

end


function [nothing] = Add_Labels( Nothing )

%Axis Label Direction of flexion/extension
label_direction_knee = '\leftarrow Extension                                               Flexion \rightarrow';
label_direction_hip = '\leftarrow Flexion                                                      Extension \rightarrow';

%Axis Label
xlabel({'Hip Angle', label_direction_hip})
ylabel({label_direction_knee, 'Knee Angle'})

end