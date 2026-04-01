%% Percent Gait Cycle Detection
clc; clear;

%% Options

Process_DataFiltering = 1 ;

%% Load Data

dataIMU = importdata('data_5.txt');

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


%% Filter Data

if Process_DataFiltering

%Filter Hip Velocity:
[hip_vel, raw_hip_vel] = FilterData( hip_vel )
disp('NOTE: FILTERING Hip Velocity Data with Butterworth Filter')

%Filter Knee Velocity:
[knee_vel, raw_knee_vel] = FilterData( knee_vel )
disp('NOTE: FILTERING Knee Velocity Data with Butterworth Filter')


figure(300); clf; hold on
title('Data Filtering')
plot(raw_knee_vel)
plot(knee_vel)
legend Raw Filtered


end


%% Computations:



%Phase Variables
X = hip_angle;
Y = hip_vel;

%Compute Phase Value
% Phase = atan2d(hip_vel,hip_angle)
Phase = atan2d(Y,X);
% Phase = atan2d(X,Y)


% Phase_360 = mod(atan2d(Y,X),360);
Phase_360 = atan2d(Y,X) + 360*(Y<0);

figure(100); clf; hold on
subplot(2,1,1); hold on;
plot(X, Y)

% plot(knee_angle, knee_vel)
xline(0); yline(0)

clf; hold on;
% subplot(2,1,2); hold on;
plot(time,Phase_360, '.-')
plot(time,hip_angle*10+200)
% plot(time,knee_angle*5-150)
yline(0)
% legend Phase 'Knee Angle'
legend Phase 'Hip Angle' 'Knee Angle'
















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




function [filtered_data, raw_data] = FilterData( raw_data )

[b,a] = butter(3,0.3);
filtered_data = filter(b,a,raw_data);
disp("Data Filtering Performed")

end