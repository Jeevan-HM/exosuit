%% aggregate_metrics_v2.m
% Deeper analysis. Does NOT modify aggregate_metrics.m. Three layers:
%   L1 (MAIN): overall whole-cycle assistance (Active & Inactive vs No-Exo)
%   L2: inter- vs intra-subject consistency of the effect (+ responder rates)
%   L3: cross-zone / antagonist story (on-target + off-target) & passive vs active
% Outputs three publication figures and a copy-pasteable text report.

clear; clc; close all;

muscles   = {'VL','RF','BF','ST'};
is_ext    = [true true false false];        % VL,RF extensors ; BF,ST flexors
cond_list = {'noexo','exoinactive','exoactive'};
hasStats  = (exist('signrank','file')==2) || license('test','Statistics_Toolbox');

% ---- publication style ----
FIG.font='Times New Roman'; FIG.fs=13; FIG.lw=2; FIG.mk=55;
% one colour per condition, used consistently across all panels
FIG.cNoexo=[0.55 0.55 0.55]; FIG.cIna=[0.47 0.67 0.19]; FIG.cAct=[0.15 0.53 0.82];
FIG.save=false; FIG.dir='paper_figures_v2'; FIG.fmt='png'; FIG.dpi=600;   % PNG export
set(groot,'defaultAxesFontName',FIG.font,'defaultTextFontName',FIG.font, ...
    'defaultLegendFontName',FIG.font,'defaultAxesFontSize',FIG.fs,'defaultAxesLineWidth',1);

%% ===== LOAD (exclude nested backups) =====
this_dir=fileparts(mfilename('fullpath')); if isempty(this_dir), this_dir=pwd; end
files=dir(fullfile(this_dir,'**','*_metrics.mat'));
keep=arrayfun(@(x) strcmp(fileparts(x.folder),this_dir) && ~contains(x.folder,'Old Version Data'), files);
files=files(keep);
if isempty(files), error('No *_metrics.mat found directly under a subject folder of %s', this_dir); end

Subject={};Speed=[];Incline=[];Muscle={};Condition={};WC=[];EX=[];FL=[];
for f=1:numel(files)
    S=load(fullfile(files(f).folder,files(f).name),'metrics'); if ~isfield(S,'metrics'), continue; end
    m=S.metrics;
    for c=1:3
        for k=1:4
            Subject{end+1,1}=char(m.subject); Speed(end+1,1)=m.speed; Incline(end+1,1)=m.incline; %#ok<*AGROW>
            Muscle{end+1,1}=muscles{k}; Condition{end+1,1}=m.conditions{c};
            WC(end+1,1)=m.wholecycle_mean(c,k);
            EX(end+1,1)=m.ext_zone_mean(c,k);
            FL(end+1,1)=m.flex_zone_mean(c,k);
        end
    end
end
D=table(Subject,Speed,Incline,Muscle,Condition,WC,EX,FL);
subs=unique(D.Subject); Ns=numel(subs);
[wc,~]=unique([D.Incline D.Speed],'rows'); Nw=size(wc,1);
fprintf('Subjects: %d | walking conditions: %d\n', Ns, Nw);

%% ===== BUILD PER-SUBJECT REDUCTIONS =====
% pooled over walking conditions -> Ns x 4 ; ci: 2=active,1=inactive vs 0=noexo
poolv=@(col,si,k,cond) mean(col(strcmp(D.Subject,subs{si})&strcmp(D.Muscle,muscles{k})&strcmp(D.Condition,cond)),'omitnan');
[redA_wc,redI_wc,redA_ex,redI_ex,redA_fl,redI_fl,redAI_wc]=deal(nan(Ns,4));
for si=1:Ns
    for k=1:4
        noW=poolv(D.WC,si,k,'noexo'); iaW=poolv(D.WC,si,k,'exoinactive'); acW=poolv(D.WC,si,k,'exoactive');
        if ~isnan(noW)&&noW~=0, redA_wc(si,k)=(noW-acW)/noW*100; redI_wc(si,k)=(noW-iaW)/noW*100; end
        if ~isnan(iaW)&&iaW~=0, redAI_wc(si,k)=(iaW-acW)/iaW*100; end   % active-control contribution
        noE=poolv(D.EX,si,k,'noexo'); iaE=poolv(D.EX,si,k,'exoinactive'); acE=poolv(D.EX,si,k,'exoactive');
        if ~isnan(noE)&&noE~=0, redA_ex(si,k)=(noE-acE)/noE*100; redI_ex(si,k)=(noE-iaE)/noE*100; end
        noF=poolv(D.FL,si,k,'noexo'); iaF=poolv(D.FL,si,k,'exoinactive'); acF=poolv(D.FL,si,k,'exoactive');
        if ~isnan(noF)&&noF~=0, redA_fl(si,k)=(noF-acF)/noF*100; redI_fl(si,k)=(noF-iaF)/noF*100; end
    end
end

% per-walking-condition whole-cycle Active reduction (for inter/intra)
redA_wc_w=nan(Ns,4,Nw);
for si=1:Ns
    for k=1:4
        for iw=1:Nw
            sel=strcmp(D.Subject,subs{si})&strcmp(D.Muscle,muscles{k})&D.Incline==wc(iw,1)&D.Speed==wc(iw,2);
            no=mean(D.WC(sel&strcmp(D.Condition,'noexo')),'omitnan');
            ac=mean(D.WC(sel&strcmp(D.Condition,'exoactive')),'omitnan');
            if ~isnan(no)&&no~=0, redA_wc_w(si,k,iw)=(no-ac)/no*100; end
        end
    end
end

% absolute whole-cycle %MVC per subject per muscle per condition (for the top panel)
absWC=nan(Ns,4,3); condK={'noexo','exoinactive','exoactive'};
for si=1:Ns
    for k=1:4
        for c=1:3, absWC(si,k,c)=poolv(D.WC,si,k,condK{c}); end
    end
end

%% ===== STATS =====
alpha=0.05;
pA=nan(1,4); dzA=nan(1,4); respA=nan(1,4);
for k=1:4
    x=redA_wc(~isnan(redA_wc(:,k)),k);
    dzA(k)=effect_dz(x); respA(k)=sum(x>0);
    pA(k)=signrank_safe(x,hasStats);
end
qA=bh_fdr(pA);

% off-target (antagonist) cells: flexors in EXT, extensors in FLEX
off_red={redA_fl(:,1),redA_fl(:,2),redA_ex(:,3),redA_ex(:,4)};
off_name={'VL(flex)','RF(flex)','BF(ext)','ST(ext)'};
pOff=cellfun(@(v) signrank_safe(v(~isnan(v)),hasStats), off_red);
qOff=bh_fdr(pOff);

% inter vs intra (whole-cycle Active reduction)
betweenSD=nan(1,4); intraSD=nan(1,4);
for k=1:4
    sm=mean(squeeze(redA_wc_w(:,k,:)),2,'omitnan');       % subject means over conditions
    sw=std(squeeze(redA_wc_w(:,k,:)),0,2,'omitnan');      % within-subject SD across conditions
    betweenSD(k)=std(sm,'omitnan'); intraSD(k)=mean(sw,'omitnan');
end

% muscle x zone group means (for the report)
Mpas=[mean(redI_ex,1,'omitnan')' mean(redI_fl,1,'omitnan')'];   % 4x2 (Ext,Flex) inactive
Mact=[mean(redA_ex,1,'omitnan')' mean(redA_fl,1,'omitnan')'];   % 4x2 active

%% ===== FIGURE L1 (MAIN): 2 panels — absolute activity (top) + reduction (bottom) =====
figHandles.v2_L1_wholecycle = plot_L1(absWC, redA_wc, redI_wc, muscles, qA, FIG);

%% ===== FIGURE L2: inter/intra heatmap (subjects x muscles) =====
figHandles.v2_L2_intersubject = plot_subject_heat(redA_wc, muscles, respA, FIG);

%% ===== FIGURE L3: cross-zone antagonist forest (passive vs active, CI + significance) =====
figHandles.v2_L3_zone = plot_zone_forest(redA_ex, redA_fl, redI_ex, redI_fl, muscles, is_ext, FIG);

if FIG.save
    outdir=fullfile(this_dir,FIG.dir); if ~exist(outdir,'dir'), mkdir(outdir); end
    fn=fieldnames(figHandles);
    for i=1:numel(fn), save_png(figHandles.(fn{i}), fullfile(outdir,[fn{i} '.' FIG.fmt]), FIG.dpi); end
    fprintf('Exported %d figures to %s\n', numel(fn), outdir);
end

%% ===== COPY-PASTEABLE REPORT =====
R=sprintf('\n>>> COPY FROM HERE - DEEP MUSCLE-ACTIVITY REPORT (v2) >>>\n');
R=[R sprintf('N=%d participants; 4 walking conditions; conditions {No-Exo, Inactive, Active}.\n',Ns)];
R=[R sprintf('Reductions are within-participant %% change vs No-Exo (positive = less activity).\n')];
R=[R sprintf('Tests: Wilcoxon signed-rank vs 0; q = Benjamini-Hochberg FDR. alpha=%.2f.\n\n',alpha)];

R=[R sprintf('--- LAYER 1: OVERALL ASSISTANCE (whole-cycle mean) ---\n')];
R=[R sprintf('%-4s %8s %8s %6s %6s %10s\n','Musc','Active%','dz','p','q','responders')];
for k=1:4
    [mA,cA]=mean_ci(redA_wc(:,k));
    R=[R sprintf('%-4s %6.1f+-%-4.1f %6.2f %6.3f %6.3f  %d/%d %s\n', muscles{k}, mA,cA, dzA(k), pA(k), qA(k), respA(k), Ns, sig_label(qA(k),alpha))];
end
R=[R sprintf('Inactive (passive) whole-cycle %% change vs No-Exo (negative = increase):\n')];
for k=1:4, R=[R sprintf('  %-4s %6.1f%%\n', muscles{k}, mean(redI_wc(:,k),'omitnan'))]; end
R=[R sprintf('Active-control contribution (Active vs Inactive) %%:\n')];
for k=1:4, R=[R sprintf('  %-4s %6.1f%%\n', muscles{k}, mean(redAI_wc(:,k),'omitnan'))]; end

R=[R sprintf('\n--- LAYER 2: INTER- vs INTRA-SUBJECT (whole-cycle Active reduction) ---\n')];
R=[R sprintf('%-4s %12s %12s %12s\n','Musc','between-SD','intra-SD','responders')];
for k=1:4, R=[R sprintf('%-4s %10.1f %11.1f %10d/%d\n', muscles{k}, betweenSD(k), intraSD(k), respA(k), Ns)]; end
R=[R sprintf('(large between-SD => person-specific benefit; small => universal responder.)\n')];

R=[R sprintf('\n--- LAYER 3: CROSS-ZONE / ANTAGONIST (Active vs No-Exo, %% reduction) ---\n')];
R=[R sprintf('%-4s %12s %12s   (* = on-target zone)\n','Musc','Ext-zone','Flex-zone')];
for k=1:4
    te=''; tf='';
    if is_ext(k), te='*'; else, tf='*'; end
    R=[R sprintf('%-4s %10.1f%1s %10.1f%1s\n', muscles{k}, Mact(k,1),te, Mact(k,2),tf)];
end
% --- all 8 muscle x zone cells, FDR across 8 (this is what the forest figure uses) ---
zoneCell={redA_ex(:,1),redA_fl(:,1),redA_ex(:,2),redA_fl(:,2),redA_ex(:,3),redA_fl(:,3),redA_ex(:,4),redA_fl(:,4)};
zoneName={'VL|ext','VL|flex','RF|ext','RF|flex','BF|ext','BF|flex','ST|ext','ST|flex'};
zoneOn =[1 0 1 0 0 1 0 1];  % on-target: extensor in ext-zone / flexor in flex-zone
p8=cellfun(@(v) signrank_safe(v(~isnan(v)),hasStats), zoneCell);
q8=bh_fdr(p8);
R=[R sprintf('All 8 muscle x zone cells (Active vs No-Exo), FDR across 8 -- MATCHES FIGURE:\n')];
for i=1:8
    ot=''; if zoneOn(i), ot='(on-target)'; end
    R=[R sprintf('  %-8s %6.1f%%  p=%.3f q=%.3f %s %s\n', zoneName{i}, mean(zoneCell{i},'omitnan'), p8(i), q8(i), sig_label(q8(i),alpha), ot)];
end
R=[R sprintf('Off-target (antagonist) cells, FDR across the 4 antagonist cells only:\n')];
for i=1:4, R=[R sprintf('  %-9s %6.1f%%  p=%.3f q=%.3f %s\n', off_name{i}, mean(off_red{i},'omitnan'), pOff(i), qOff(i), sig_label(qOff(i),alpha))]; end
R=[R sprintf('Passive (Inactive vs No-Exo) zone %% change (negative = increase):\n')];
for k=1:4, R=[R sprintf('  %-4s Ext %6.1f  Flex %6.1f\n', muscles{k}, Mpas(k,1), Mpas(k,2))]; end
R=[R sprintf('<<< COPY TO HERE <<<\n')];
fprintf('%s',R);
fid=fopen(fullfile(this_dir,'results_report_v2.txt'),'w');
if fid>0, fprintf(fid,'%s',R); fclose(fid); fprintf('Report saved to results_report_v2.txt\n'); end

%% ============================ LOCAL FUNCTIONS ============================
function hf=plot_L1(absWC, redA, redI, muscles, qA, FIG)
    % 2 panels. Top: absolute whole-cycle activity for No-Exo/Inactive/Active.
    % Bottom: reduction vs No-Exo (Active & Inactive) with FDR stars.
    X=1:4; Ns=size(redA,1);
    cCond=[FIG.cNoexo; FIG.cIna; FIG.cAct]; cLab={'No-Exo','Inactive','Active'};
    hf=figure('Name','v2_L1_wholecycle','Color','w','Units','centimeters','Position',[2 2 9 14]);

    % ---- TOP: absolute activity, three conditions ----
    subplot(2,1,1); hold on; offs=[-0.22 0 0.22];
    for c=1:3
        mm=arrayfun(@(k) mean(absWC(:,k,c),'omitnan'),X);
        cc=arrayfun(@(k) ci95(absWC(:,k,c)),X);
        errorbar(X+offs(c),mm,cc,'o','Color',cCond(c,:),'MarkerFaceColor',cCond(c,:), ...
            'MarkerSize',5.5,'LineWidth',FIG.lw-0.4,'CapSize',5,'DisplayName',cLab{c});
    end
    set(gca,'XTick',X,'XTickLabel',muscles); xlim([0.5 4.5]); ylim([0 inf]);
    ylabel('Activity (% MVC)');
    legend('Location','northoutside','Orientation','horizontal','Box','off'); box off;

    % ---- BOTTOM: reduction vs No-Exo ----
    subplot(2,1,2); hold on; off=0.16;
    mA=mean(redA,1,'omitnan'); mI=mean(redI,1,'omitnan');
    cA=arrayfun(@(k) ci95(redA(:,k)),X); cI=arrayfun(@(k) ci95(redI(:,k)),X);
    yline(0,'-','Color',[0.75 0.75 0.75],'LineWidth',1,'HandleVisibility','off');
    for k=X
        jt=(rand(Ns,1)-0.5)*0.10;
        scatter((k-off)+jt,redA(:,k),FIG.mk*0.3,FIG.cAct,'filled','MarkerFaceAlpha',0.22,'HandleVisibility','off');
        scatter((k+off)+jt,redI(:,k),FIG.mk*0.3,FIG.cIna,'filled','MarkerFaceAlpha',0.25,'HandleVisibility','off');
    end
    errorbar(X-off,mA,cA,'o','Color',FIG.cAct,'MarkerFaceColor',FIG.cAct,'MarkerSize',5.5,'LineWidth',FIG.lw-0.4,'CapSize',5,'DisplayName','Active');
    errorbar(X+off,mI,cI,'s','Color',FIG.cIna,'MarkerFaceColor',FIG.cIna,'MarkerSize',6,'LineWidth',FIG.lw-0.4,'CapSize',5,'DisplayName','Inactive');
    for k=X, s=stars(qA(k)); if ~isempty(s), text(k-off,mA(k)+cA(k)+4,s,'HorizontalAlignment','center','FontSize',FIG.fs); end, end
    set(gca,'XTick',X,'XTickLabel',muscles); xlim([0.5 4.5]); ylabel('Reduction vs No-Exo (%)');
    box off;   % colours match the top-panel legend, so no second legend needed
end

function hf=plot_subject_heat(redA, muscles, resp, FIG)
    [Ns,~]=size(redA);
    hf=figure('Name','v2_L2_intersubject','Color','w','Units','centimeters','Position',[2 2 9 9]);
    imagesc(redA); colormap(divmap());
    cmax=max(abs(redA(:)),[],'omitnan'); if ~(cmax>0), cmax=1; end; caxis([-cmax cmax]);
    cb=colorbar; cb.Label.String='Reduction vs No-Exo (%)';
    for i=1:Ns, for j=1:4
        if ~isnan(redA(i,j)), text(j,i,sprintf('%.0f',redA(i,j)),'HorizontalAlignment','center','FontSize',FIG.fs-2,'Color',[0 0 0]); end
    end, end
    set(gca,'XTick',1:4,'XTickLabel',muscles,'YTick',1:Ns, ...
        'YTickLabel',arrayfun(@(i) sprintf('S%d',i),1:Ns,'uni',0),'TickLength',[0 0]);
    xlabel(sprintf('Muscle (responders: %s)', strjoin(arrayfun(@(k) sprintf('%s %d/%d',muscles{k},resp(k),Ns),1:4,'uni',0),', ')));
    ylabel('Participant');
end

function hf=plot_zone_forest(redA_ex, redA_fl, redI_ex, redI_fl, muscles, is_ext, FIG)
    % Forest of muscle x zone. Each row: Inactive (open, passive) and Active
    % (filled, blue, with 95% CI) change vs No-Exo, connected by a line to show
    % the passive->active reversal. On-target zone label in bold; * = significant
    % active reduction (FDR across the 8 cells). x>0 = reduction.
    hasStats = (exist('signrank','file')==2) || license('test','Statistics_Toolbox');
    zoneA={redA_ex,redA_fl}; zoneI={redI_ex,redI_fl}; zn={'ext','flex'};
    nr=8; mAct=nan(1,nr); ciAct=nan(1,nr); mPas=nan(1,nr); pAct=nan(1,nr);
    lab=cell(1,nr); onflag=false(1,nr); r=0;
    for k=1:4
        for z=1:2
            r=r+1;
            a=zoneA{z}(:,k); i=zoneI{z}(:,k);
            mAct(r)=mean(a,'omitnan'); ciAct(r)=ci95(a); mPas(r)=mean(i,'omitnan');
            if hasStats && sum(~isnan(a))>=2, pAct(r)=signrank(a(~isnan(a))); end
            lab{r}=sprintf('%s | %s', muscles{k}, zn{z});
            onflag(r)=(z==1 && is_ext(k)) || (z==2 && ~is_ext(k));
        end
    end
    qAct=bh_fdr(pAct);
    y=1:nr;

    hf=figure('Name','v2_L3_zone','Color','w','Units','centimeters','Position',[2 2 11 11]); hold on;
    xline(0,'-','Color',[0.75 0.75 0.75],'LineWidth',1,'HandleVisibility','off');
    for r=1:nr
        plot([mPas(r) mAct(r)],[y(r) y(r)],'-','Color',[0.75 0.75 0.75],'LineWidth',1,'HandleVisibility','off');
        errorbar(mAct(r),y(r),ciAct(r),'horizontal','o','Color',FIG.cAct, ...
            'MarkerFaceColor',FIG.cAct,'MarkerSize',6,'LineWidth',FIG.lw-0.4,'CapSize',5,'HandleVisibility','off');
        plot(mPas(r),y(r),'o','MarkerEdgeColor',FIG.cIna,'MarkerFaceColor','none', ...
            'MarkerSize',6,'LineWidth',1.4,'HandleVisibility','off');
        s=stars(qAct(r));
        if ~isempty(s), text(mAct(r)+ciAct(r)+2,y(r),s,'HorizontalAlignment','left','VerticalAlignment','middle','FontSize',FIG.fs); end
    end
    % bold labels for on-target rows
    set(gca,'YTick',y,'YTickLabel',[],'YDir','reverse','TickLength',[0 0]);
    xl=xlim; xlim([min(xl(1),min(mPas)-8) xl(2)+6]); xl=xlim;
    for r=1:nr
        fw='normal'; if onflag(r), fw='bold'; end
        text(xl(1)-1,y(r),lab{r},'HorizontalAlignment','right','FontWeight',fw,'FontSize',FIG.fs-1);
    end
    ylim([0.4 nr+0.6]);
    xlabel('Change vs No-Exo (%)   (positive = reduction)');
    % legend proxies
    h1=plot(nan,nan,'o','MarkerEdgeColor',FIG.cIna,'MarkerFaceColor','none','LineWidth',1.4,'DisplayName','Inactive (passive)');
    h2=plot(nan,nan,'o','MarkerEdgeColor',FIG.cAct,'MarkerFaceColor',FIG.cAct,'DisplayName','Active');
    legend([h1 h2],'Location','southoutside','Orientation','horizontal','Box','off');
    box off;
end

function c=divmap()
    n=32;
    % MUTED diverging palette: soft salmon (increase) -> white -> soft sage
    % (reduction). Less saturated than a pure red/green so an all-increase panel
    % doesn't read as alarming.
    top=[linspace(0.87,1,n)' linspace(0.60,1,n)' linspace(0.57,1,n)'];   % soft red  -> white
    bot=[linspace(1,0.55,n)' linspace(1,0.77,n)' linspace(1,0.60,n)'];   % white -> soft green
    c=[top;bot];
end

function c=ci95(x)
    x=x(~isnan(x)); n=numel(x); if n<2, c=0; return; end
    c=tcrit95(n-1)*std(x)/sqrt(n);
end
function [m,c]=mean_ci(x), m=mean(x,'omitnan'); c=ci95(x); end
function dz=effect_dz(x)
    x=x(~isnan(x)); if numel(x)<2||std(x)==0, dz=NaN; else, dz=mean(x)/std(x); end
end
function p=signrank_safe(x,hasStats)
    x=x(~isnan(x)); if hasStats&&numel(x)>=2, p=signrank(x); else, p=NaN; end
end
function q=bh_fdr(p)
    p=p(:)'; m=numel(p); q=nan(1,m); ok=~isnan(p); pp=p(ok); mm=numel(pp);
    if mm==0, return; end
    [ps,ix]=sort(pp); qs=ps.*mm./(1:mm);
    for i=mm-1:-1:1, qs(i)=min(qs(i),qs(i+1)); end
    qv=nan(1,mm); qv(ix)=min(qs,1); q(ok)=qv;
end
function tc=tcrit95(df)
    if df<1, tc=NaN; return; end
    if exist('tinv','file')==2, tc=tinv(0.975,df); return; end
    tbl=[12.71 4.303 3.182 2.776 2.571 2.447 2.365 2.306 2.262 2.228];
    if df<=10, tc=tbl(df); elseif df<=20, tc=2.086; elseif df<=30, tc=2.042; else, tc=1.96; end
end
function s=stars(p)
    if isnan(p), s=''; elseif p<0.001, s='***'; elseif p<0.01, s='**'; elseif p<0.05, s='*'; else, s=''; end
end
function s=sig_label(q,alpha)
    if isnan(q), s='n/a'; elseif q<0.001, s='*** sig'; elseif q<0.01, s='**  sig'; elseif q<alpha, s='*   sig'; else, s='n.s.'; end
end
function save_png(h,file,dpi)
    try, exportgraphics(h,file,'Resolution',dpi);
    catch
        set(h,'Units','centimeters'); p=get(h,'Position');
        set(h,'PaperUnits','centimeters','PaperPositionMode','manual','PaperSize',[p(3) p(4)],'PaperPosition',[0 0 p(3) p(4)]);
        print(h,file,'-dpng',sprintf('-r%d',dpi));
    end
end
