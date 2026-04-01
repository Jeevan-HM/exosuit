%% Joint Angle Estimation using IMUs from two Pixhawks, and VICON data plot
clc; clear; %clf;

for indexShiftNew = 150%:180
% for indexShiftNew = 500:-10:0 

for Method = [5]  %Method 1 = No Alignment; Method 2 = Aligned to initial frame
    clearvars -except Method indexShiftNew
    
    
    %% Options / Plot Figures
    
    PlotRawData = 1;
    Plot_Method_Comparison = 1;
    PlotEuler = 0;
    
    ZeroJointAngles = 1;
    
    
    
    %% IMU  Pixhawk Data    
    
    
    dataIMU = importdata('OUTPUT_prueba.txt');
    % dataIMU = importdata('Data 11_02 Torque Platform/data_imu_torque_platform_11_02.txt');
    % dataIMU = importdata('Data Simple Walk/OUTPUT_DATA.txt');
    time = dataIMU(:,1);
    
    quatShank = quaternion( dataIMU(:,2:5) );
    quatShankRaw = ( dataIMU(:,2:5) );
    
    
    quatThigh = quaternion( dataIMU(:,9:12) );
    quatThighRaw = ( dataIMU(:,9:12) );


    

    %% % Create Quaternion objects for computations:
%     quatShank = quaternion( data_quat_shank );
%     quatThigh = quaternion( data_quat_thigh );
    % quatTorso = quaternion( dataIMU(:,16:19) );
    
   
          %% Plot Raw Euler of Each IMU
%         quatThighNew = quatThigh.compact
%         [rollThighNew,pitchThighNew,yawThighNew] = Quat2Euler( quatThighNew );
%         
%         quatShankNew = quatShank.compact
%         [rollShankNew,pitchShankNew,yawShankNew] = Quat2Euler( quatShankNew );
% 
%         figure(22); clf; hold on
%         title('Shank')
%         plot(rollShankNew)
%         plot(pitchShankNew)
%         plot(yawShankNew)
%         legend roll pitch yaw
%         grid on
%         
%         figure(33); clf; hold on
%         title('Thigh')
%         plot(rollThighNew)
%         plot(pitchThighNew)
%         plot(yawThighNew)
%         legend roll pitch yaw
%         grid on
    

    %% Align the IMUs to their initial frames, and then align to the frame that best represent the human saggital plane
    
    if Method == 2
        disp('Method 2')
        %Get inifial quaternion reading
        quatThigh0 = quatThigh(1);
        quatShank0 = quatShank(1);    


        %Align to Respective Initial Frame
        for i = 1:length(dataIMU)
            quatShank(i) = conj(quatShank0)*quatShank(i);
            quatThigh(i) = conj(quatThigh0)*quatThigh(i);
            %     quatTorso(i) = conj(quat0)*quatTorso(i);
        end
        
    end
    
    
    if Method == 3
        %THIS METHOD DOES NOT YIELD GOOD RESULTS
        %Align to frame that best represents the human saggital plane.
        %OR: eliminate misalignment between top and bottom IMUs reference frame
        disp('Method 3')
        quat0 = quatShank(1);
        for i = 1:length(dataIMU)
            quatShank(i) = conj(quat0)*quatShank(i);
            quatThigh(i) = conj(quat0)*quatThigh(i);
        end
%         disp('Note" only 1 IMU is being aligned to eliminate misalignment between top and bottom IMUs reference frame')
    end
   
    
    if Method == 4
       %Compute the misalignment between the sensors, and substract it
       disp('Method 4')
       
        %Get inifial quaternion reading
        quatThigh0 = quatThigh(1);
        quatShank0 = quatShank(1);
        
        quat0_diff = conj(quatThigh0)*quatShank0;
        
%         [angle1, angle2, angle3] = Quat2Euler( quat0_diff )

     for i = 1:length(dataIMU)
        quatShank(i) = conj(quat0_diff)*quatShank(i);
%         quatThigh(i) = conj(quat0_diff)*quatThigh(i);
     end
        
     %Align to Respective Initial Frame
     for i = 1:length(dataIMU)
         quatShank(i) = conj(quatShank0)*quatShank(i);
         quatThigh(i) = conj(quatThigh0)*quatThigh(i);
         %     quatTorso(i) = conj(quat0)*quatTorso(i);
     end
     
     
    end
    
    
    %% Compute Quaternion Difference
    
    % for i = 1:length(dataIMU)
    % QuatKnee(i) = conj(quatThigh(i))*quatShank(i);
    % QuatHip(i) = conj(quatTorso(i))*quatThigh(i);
    % end
    
    %Modified from George's suggestion google doc Oct 30
    for i = 1:length(dataIMU)
        QuatKnee(i) = conj(quatShank(i))*quatThigh(i);
        % QuatHip(i) = conj(quatTorso(i))*quatThigh(i);
    end
    
    
    QuatKneeMat = QuatKnee.compact;
    % QuatHipMat = QuatHip.compact;
    
    
    %% Convert to Euler Angles
    
    %Knee
    [rollKneeQuat, pitchKneeQuat, yawKneeQuat] = Quat2Euler( QuatKneeMat );
    AngleKnee = -pitchKneeQuat;
    AngleKneeRaw2 = pitchKneeQuat;
    
    % %Hip
    % [rollHipQuat, pitchHipQuat, yawHipQuat] = Quat2Euler( QuatHipMat );
    % AngleHip = -pitchHipQuat;
    
        
    
    
    %% Rotation Matrix Calculations:
    if Method == 5
    disp('Method 5: Rotation Matrix Method')
    clear AngleKnee AngleHip
    
    quatShank = quaternion( quatShankRaw );
    quatThigh = quaternion( quatThighRaw );
      
    %Get inifial quaternion reading
    quatThigh0 = quatThigh(1);
    quatShank0 = quatShank(1);
%     qdiff = conj(quatShank0)*quatThigh0;

    %Align to Respective Initial Frame
    for i = 1:length(dataIMU)
        quatShank(i) = conj(quatShank0)*quatShank(i);
        quatThigh(i) = conj(quatThigh0)*quatThigh(i);
        %     quatTorso(i) = conj(quat0)*quatTorso(i);
%         quatThigh(i) = conj(qdiff)*quatThigh(i);
    end
    
    
    
    %Convert to Rotation Matrix:
    rotShank = rotmat(quatShank, 'frame');
    rotThigh = rotmat(quatThigh, 'frame');
%     rotTorso = rotmat(quatTorso, 'frame');
    
    axisRot = 3; %Axis of interest of the Rotation Matrix
    %Note: Independent of the axis of rotation, the euler angle decomposition of the Relative Rotation matrix yields the same results
    
    for i = 1:length(dataIMU)
    %     Zshank(i,:) = rotShank(:,3,i);
    %     Zthigh(i,:) = rotThigh(:,3,i);
        Zshank = rotShank(:,axisRot,i);
        Zthigh = rotThigh(:,axisRot,i);
%         Ztorso = rotTorso(:,axisRot,i);
    
        %Paper Calculations:
        AngleKnee(i) = - atan2d( sqrt(1-(norm(cross(Zshank, Zthigh))^2)) , norm(cross(Zshank, Zthigh)) );
        AngleKneeRaw5(i) = -AngleKnee(i);


%         RelRot = inv(rotShank(:,:,i))*(rotThigh(:,:,i));
%     
%         eulRelRot = rotm2eul(RelRot);
%     
%         AngleKnee(i) = rad2deg( eulRelRot(3) ); %2nd val
%     
    
    
    end
    
    end
    
    %% Absolute angle between two quaternions
    
    % % This computation method was found in a thesis. Reference: Ahmed, A. (2019). Developing a prototype using IMUs to do 24 hours measurement of knee joint mobility in children with Cerebral Palsy. http://lup.lub.lu.se/student-papers/record/8996696
    % quatShanknormalized = quatShank.normalize;
    % quatThighnormalized = quatThigh.normalize;
    %
    % quatShankMat = quatShanknormalized.compact;
    % quatThighMat = quatThighnormalized.compact;
    %
    % quat1_w = quatShankMat(:,1);
    % quat1_x = quatShankMat(:,2);
    % quat1_y = quatShankMat(:,3);
    % quat1_z = quatShankMat(:,4);
    %
    % quat2_w = quatThighMat(:,1);
    % quat2_x = quatThighMat(:,2);
    % quat2_y = quatThighMat(:,3);
    % quat2_z = quatThighMat(:,4);
    %
    % AngleKnee = 57.2958*2*acos(abs(quat1_w.*quat2_w + quat1_x.*quat2_x + quat1_y.*quat2_y+quat1_z.*quat2_z));
    
    
    %% Zero Joint Angles from Quaternion:
    if ZeroJointAngles
    % yawKnee0 = mean(yawKnee(1:600));
    % yawKnee = yawKnee - yawKnee0;
    % pitchHip0 = mean(pitchHip(1:600));
    % pitchHip = pitchHip - pitchHip0;
    % pitchHip = -pitchHip; %flip to Match Vicon orientation
    
    %Quaternion Computations:
    NoSamples = 10;
    % NoSamples = 600; % number of samples to average the zero joint angles
    AngleKnee0 = mean(AngleKnee(1:NoSamples));
    AngleKnee = AngleKnee - AngleKnee0;
    % AngleHip0 = mean(AngleHip(1:NoSamples));
    % AngleHip = AngleHip - AngleHip0;
    
    % AngleKnee = AngleKnee + 6;
    % disp('NOTE: Manual Shift to the Joint Angle was added')
    end
    
    
    %% Plot IMU Knee Joint Angles
    % Method Comparison
    
    figure(15); hold on;
    set(gca, 'FontSize',16)
    
%     plot(time,AngleKnee,'LineWidth',3)
    
    if Method < 3
        plot(time,AngleKnee,'LineWidth',3)
    else
        plot(time,AngleKnee, '--', 'LineWidth',3)
    end
    
    title('Analog Knee Joint Angle from Pixhawk IMU')
    xlabel('Time [sec]'); %xlim([30 70])
    ylabel('Knee Joint Angle [deg]')
    grid on;% grid minor
%     xlim([0 50]); ylim([-10 100])
    %Check Legend Below
    
% end

% %Legend Methods
% yline(0); grid minor;  
% legend 'No Alignment'  'Aligned Each IMU To Its Respective Initial Frame' % 'Aligned All To Shank Initial Frame'
% % legend Method1 Method2 Method3 Method4

%% Plot Euler Angles Knee
if PlotEuler
    time = time_thigh;
    figure(4); clf; hold on
    % plot(timeVicon, kneeAngle_Vicon,'LineWidth',3)
    plot(time,[rollKneeQuat, pitchKneeQuat, yawKneeQuat], 'LineWidth',2)
    % legend MoCap Roll-Knee Pitch-Knee Yaw-Knee
    legend Roll-Knee Pitch-Knee Yaw-Knee
    xlabel('Time [sec]'); %xlim([18 70])
    ylabel('Knee Joint Angle [deg]')
    title('Knee Joint Angle')
    grid on
end

return

%% MOCAP Data

%Load Data:
dataMoCapStruct = importdata('Data_Vicon/IMU_pixhawk_07mps.csv');
dataMocap = dataMoCapStruct.data;
hipAngle_Vicon = dataMocap(:,45);
kneeAngle_Vicon = dataMocap(:,57);
% kneeAngle_Vicon(1:10)

%Time Vicon:
freq = 100; %[hz] Vicon Frequency
dtVicon = 1/freq; %[sec] Time between samples
timeVicon = 0:dtVicon:(length(dataMocap)-1)*dtVicon; %[sec] Vicon Time vector 


%Zero Joint Angles from Vicon
NoSamples = 400; % number of samples to average the zero joint angles
kneeAngle0 = mean(kneeAngle_Vicon(1:NoSamples));
kneeAngle_Vicon = kneeAngle_Vicon - kneeAngle0;
% hipAngle0 = mean(hipAngle_Vicon(1:NoSamples));
% hipAngle_Vicon = hipAngle_Vicon - hipAngle0;



%% Identify Peak for cero time sync

%Find Knee angle first peak:
Angles_Shift = -pitchKneeQuat; %Select which angle to use to match Vicon times. (Select one that has smooth peaks)
[~,peak_KneeIMU] = findpeaks(Angles_Shift,'MinPeakHeight', max([Angles_Shift(1)*1.2, 10]) );
t0IMU = time(peak_KneeIMU(1));


%Identify Vicon Peak for cero time sync
[~,peak_KneeVicon] = findpeaks(kneeAngle_Vicon,'MinPeakHeight',20);
t0Vicon = timeVicon(peak_KneeVicon(1));


% % Plot IMU and VICON time Sync:
% % Plot IMU Data Peaks:
% figure(100); clf; hold on
% title('Vicon and IMU Time Sync')
% plot(time, Angles_Shift)
% legend 'Angle IMU'
% plot(time(peak_KneeIMU),Angles_Shift(peak_KneeIMU),'*', 'DisplayName','Peaks IMU Angle') %Plot Peaks
% %Plot Vicon Peaks:
% plot(timeVicon, kneeAngle_Vicon, 'DisplayName', 'Vicon Angle')
% plot(timeVicon(peak_KneeVicon), kneeAngle_Vicon(peak_KneeVicon),'*', 'DisplayName', 'Peaks Vicon')
% xlabel('Time [sec]')
% ylabel('Joint Angle')


%Adjust Vicon time to sync IMU and Vicon data sets
dt_sync = t0Vicon - t0IMU;
timeVicon = timeVicon - dt_sync;



%% Plot Knee Joint Angles

if ~Plot_Method_Comparison
    figure(21); clf; hold on
    % subplot(2,1,1); hold on

    plot(timeVicon,kneeAngle_Vicon,'LineWidth',5) %Vicon
    plot(time,AngleKnee,'MarkerSize',15)
    % plot(time,[rollKneeQuat,-pitchKneeQuat,-yawKneeQuat],'.-','MarkerSize',20) %Euler Angles
    yline(0)
    legend Vicon IMU Location NE
    % legend Vicon Roll Pitch Yaw Location NE

    title('Knee Joint Angle, Sit #3')
    xlabel('Time [sec]'); %xlim([30 70])
    ylabel('Knee Joint Angle [deg]')
    grid on; grid minor
    xlim([5 28])
    % ylim([-1 51])
    text(mean(xlim),40,['Shift = ',num2str(index_shift)], 'FontSize',16)
end

%% Plot Method Comparison

if Plot_Method_Comparison
    if Method == 2
    figure(21); clf; hold on
    plot(timeVicon,kneeAngle_Vicon,'LineWidth',5) %Vicon
    plot(time,AngleKnee,'MarkerSize',15)
    end
    figure(21);
    % plot(time,AngleKnee,'MarkerSize',15)

    title('Knee Joint Angle, Walking 0.7 m/s')
    xlabel('Time [sec]'); %xlim([30 70])
    ylabel('Knee Joint Angle [deg]')

    if Method == 5
    plot(time,AngleKnee,'MarkerSize',15)
    yline(0)
    text(10,40,['Shift = ',num2str(index_shift)], 'FontSize',16)
    legend Vicon 'IMU Quat' 'IMU Rot Mat'
    grid on; grid minor;
    end
end

end
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
