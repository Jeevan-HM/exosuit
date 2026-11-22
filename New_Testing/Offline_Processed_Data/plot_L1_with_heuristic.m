%% plot_L1_with_heuristic.m
% Fig. 11 (v2_L1_wholecycle) with the heuristic controller added to the bottom panel.
% Replaces v2_L1_wholecycle + v2_controller_comparison with ONE figure.
%   Top    : whole-cycle activity (%MVC), No-Exo / Inactive / Active  (unchanged from aggregate_metrics_v2.m)
%   Bottom : whole-cycle reduction vs No-Exo; layout set by LAYOUT (see options)
%
% Data and statistics are copied from the two original scripts (neither is modified):
%   Inactive/Active : aggregate_metrics_v2.m  (pooled over the 4 walking conditions)
%   Heuristic (+RL) : controller_comparison.m (0% grade, 1.2 m/s only; the heuristic
%                     controller was tested only in that condition)
% NOTE: the heuristic was tested in ONE walking condition, while Inactive/Active are pooled over
% four. LAYOUT='split' (default) or 'grouped' compares the heuristic against RL from the SAME
% condition, so the comparison is like with like.
%
% Put this file next to aggregate_metrics_v2.m / controller_comparison.m (Offline_Processed_Data).
% R2020a compatible.

clear; clc; close all;

muscles  = {'VL','RF','BF','ST'};
hasStats = (exist('signrank','file')==2) || license('test','Statistics_Toolbox');
COND_H   = 'inc0_spd1.2';           % condition where the heuristic controller was tested

% ---- options ----
LAYOUT      = 'split';     % how the heuristic is compared fairly (both keep ONE figure):
                           %  'split'  : bottom row split into two panels with a shared y-axis:
                           %             (b) all walking conditions: Inactive vs Active
                           %             (c) 0% grade, 1.2 m/s:      Heuristic vs RL (same condition)
                           %  'grouped': one bottom panel; per muscle Inactive | Active (pooled) and,
                           %             on a shaded background, Heuristic | RL at 0%/1.2 m/s
                           %  'simple' : one bottom panel, Inactive | Heuristic | Active (no matched RL)
BOTTOM_YDIR = 'reverse';   % 'reverse': down = less activity (like the top panel); 'normal': original

% ---- publication style (same as aggregate_metrics_v2.m / controller_comparison.m) ----
FIG.font='Times New Roman'; FIG.fs=14; FIG.lw=1.8; FIG.mk=60;   % fs 11 suits a 9-cm-wide column figure
FIG.cNoexo=[0.55 0.55 0.55]; FIG.cIna=[0.47 0.67 0.19]; FIG.cAct=[0.15 0.53 0.82];
FIG.cHeur=[0.85 0.50 0.15];
FIG.save=false; FIG.dir='paper_figures_v2'; FIG.name='v2_L1_wholecycle_heuristic'; FIG.dpi=600;
set(groot,'defaultAxesFontName',FIG.font,'defaultTextFontName',FIG.font, ...
    'defaultLegendFontName',FIG.font,'defaultAxesFontSize',FIG.fs,'defaultAxesLineWidth',1);
rng(1);   % fixed jitter, so the figure is identical every run

this_dir=fileparts(mfilename('fullpath')); if isempty(this_dir), this_dir=pwd; end

%% ===================== INACTIVE / ACTIVE (as in aggregate_metrics_v2.m) =====================
files=dir(fullfile(this_dir,'**','*_metrics.mat'));
keep=arrayfun(@(x) strcmp(fileparts(x.folder),this_dir) && ~contains(x.folder,'Old Version Data'), files);
files=files(keep);
if isempty(files), error('No *_metrics.mat found directly under a subject folder of %s', this_dir); end

Subject={}; Muscle={}; Condition={}; WC=[];
for f=1:numel(files)
    S=load(fullfile(files(f).folder,files(f).name),'metrics'); if ~isfield(S,'metrics'), continue; end
    m=S.metrics;
    for c=1:3
        for k=1:4
            Subject{end+1,1}=char(m.subject); %#ok<*AGROW>
            Muscle{end+1,1}=muscles{k}; Condition{end+1,1}=m.conditions{c};
            WC(end+1,1)=m.wholecycle_mean(c,k);
        end
    end
end
D=table(Subject,Muscle,Condition,WC);
subs=unique(D.Subject); Ns=numel(subs);

poolv=@(si,k,cond) mean(D.WC(strcmp(D.Subject,subs{si})&strcmp(D.Muscle,muscles{k})&strcmp(D.Condition,cond)),'omitnan');
condK={'noexo','exoinactive','exoactive'};
absWC=nan(Ns,4,3); redA=nan(Ns,4); redI=nan(Ns,4);
for si=1:Ns
    for k=1:4
        for c=1:3, absWC(si,k,c)=poolv(si,k,condK{c}); end
        noW=absWC(si,k,1); iaW=absWC(si,k,2); acW=absWC(si,k,3);
        if ~isnan(noW)&&noW~=0, redA(si,k)=(noW-acW)/noW*100; redI(si,k)=(noW-iaW)/noW*100; end
    end
end
pA=arrayfun(@(k) signrank_safe(redA(:,k),hasStats),1:4); qA=bh_fdr(pA);

%% ===================== HEURISTIC (+RL) at 0% / 1.2 m/s (as in controller_comparison.m) =====================
bf=dir(fullfile(this_dir,'*',['Processed_' COND_H '_baseline_trial1.mat']));
subsH={};
for i=1:numel(bf)
    if ~strcmp(fileparts(bf(i).folder),this_dir) || contains(bf(i).folder,'Old Version Data'), continue; end
    [~,sn]=fileparts(bf(i).folder); subsH{end+1}=sn; %#ok<SAGROW>
end
subsH=unique(subsH); NsH=numel(subsH);
if NsH==0, error('No baseline files found for condition %s under %s', COND_H, this_dir); end

redH=nan(NsH,4); redRL=nan(NsH,4);
for si=1:NsH
    sd=fullfile(this_dir,subsH{si});
    fno=fullfile(sd,['Processed_' COND_H '_noexo_trial1.mat']);
    fbl=fullfile(sd,['Processed_' COND_H '_baseline_trial1.mat']);
    d_rl=dir(fullfile(sd,['Processed_' COND_H '_active_rl_trial*.mat']));
    if exist(fno,'file')~=2 || exist(fbl,'file')~=2 || isempty(d_rl)
        warning('%s: missing a file for %s, skipping.', subsH{si}, COND_H); continue;
    end
    if numel(d_rl)==1
        frl=fullfile(sd,d_rl(1).name);
    else
        qbest=-inf;
        for j=1:numel(d_rl)
            fp=fullfile(sd,d_rl(j).name); qq=trial_quality(fp,muscles);
            if qq>qbest, qbest=qq; frl=fp; end
        end
    end
    no=wholecycle(fno,muscles); bl=wholecycle(fbl,muscles); rl=wholecycle(frl,muscles);
    ok=no~=0 & ~isnan(no);
    redH(si,ok)=(no(ok)-bl(ok))./no(ok)*100;
    redRL(si,ok)=(no(ok)-rl(ok))./no(ok)*100;
end
pH =arrayfun(@(k) signrank_safe(redH(:,k), hasStats),1:4); qH =bh_fdr(pH);
pRL=arrayfun(@(k) signrank_safe(redRL(:,k),hasStats),1:4); qRL=bh_fdr(pRL);

%% ===================== FIGURE =====================
% All axes are placed at fixed positions (normalized units) so the panels line up:
% one shared legend on top, top panel full width, bottom panel(s) of equal height.
X=1:4;
hf=figure('Name',FIG.name,'Color','w','Units','centimeters','Position',[2 2 9 13]);
Lm=0.19; Rm=0.03; Gap=0.11; W=1-Lm-Rm;   % Gap leaves room for the y tick numbers of panel (c)
posLeg =[Lm 0.935 W 0.05];
posTop =[Lm 0.60  W 0.31];
posBL  =[Lm 0.08  (W-Gap)/2 0.38];
posBR  =[Lm+(W+Gap)/2 0.08 (W-Gap)/2 0.38];
posBF  =[Lm 0.08  W 0.38];

% ---- (a) TOP: absolute activity, three conditions ----
axA=axes(hf,'Position',posTop); hold(axA,'on');
cCond=[FIG.cNoexo; FIG.cIna; FIG.cAct]; cLab={'No-Exo','Inactive','Active'}; offs=[-0.22 0 0.22];
hTop=gobjects(1,3);
for c=1:3
    mm=arrayfun(@(k) mean(absWC(:,k,c),'omitnan'),X);
    cc=arrayfun(@(k) ci95(absWC(:,k,c)),X);
    hTop(c)=errorbar(axA,X+offs(c),mm,cc,'o','Color',cCond(c,:),'MarkerFaceColor',cCond(c,:), ...
        'MarkerSize',5,'LineWidth',FIG.lw-0.4,'CapSize',4);
end
set(axA,'XTick',X,'XTickLabel',muscles); xlim(axA,[0.5 4.5]); ylim(axA,[0 inf]);
ylabel(axA,'Activity (% MVC)'); box(axA,'off');
text(axA,-0.1,0.5,'(a)','Units','normalized','HorizontalAlignment','right','VerticalAlignment','middle','FontSize',FIG.fs);   % left of the y-label

% ---- BOTTOM ----
ttlB='(b) All walking conditions'; ttlC='(c) 0% grade, 1.2 m/s';
switch lower(LAYOUT)
    case 'split'
        axB=axes(hf,'Position',posBL);
        reduction_panel(axB,{redI,redA},{FIG.cIna,FIG.cAct},{'s','o'},{true,true},{nan(1,4),qA}, ...
            [-0.16 0.16],[],muscles,FIG);
        axC=axes(hf,'Position',posBR);
        reduction_panel(axC,{redH,redRL},{FIG.cHeur,FIG.cAct},{'^','o'},{true,true},{qH,qRL}, ...
            [-0.16 0.16],[],muscles,FIG);
        title(axB,ttlB,'FontWeight','normal','FontSize',FIG.fs-1);
        title(axC,ttlC,'FontWeight','normal','FontSize',FIG.fs-1);
        axBot=[axB axC]; vals={redI,redA,redH,redRL};
    case 'grouped'
        axB=axes(hf,'Position',posBF);
        reduction_panel(axB,{redI,redA,redH,redRL},{FIG.cIna,FIG.cAct,FIG.cHeur,FIG.cAct}, ...
            {'s','o','^','o'},{true,true,true,true},{nan(1,4),qA,qH,qRL}, ...
            [-0.32 -0.13 0.13 0.32],[0.03 0.45],muscles,FIG);
        title(axB,'Shaded: 0% grade, 1.2 m/s','FontWeight','normal','FontSize',FIG.fs-1);
        axBot=axB; vals={redI,redA,redH,redRL};
    otherwise   % 'simple'
        axB=axes(hf,'Position',posBF);
        reduction_panel(axB,{redI,redH,redA},{FIG.cIna,FIG.cHeur,FIG.cAct},{'s','^','o'}, ...
            {true,true,true},{nan(1,4),qH,qA},[-0.22 0 0.22],[],muscles,FIG);
        axBot=axB; vals={redI,redH,redA};
end

% common y-range for all bottom panels, rounded to 25 %, covering every participant dot
v=cell2mat(cellfun(@(x) x(:),vals(:),'uni',0)); v=v(isfinite(v));   % one long column
yl=[floor((min(v,[],'omitnan')-5)/25)*25, ceil((max(v,[],'omitnan')+10)/25)*25];
for ax=axBot
    ylim(ax,yl); set(ax,'YDir',BOTTOM_YDIR,'YTick',yl(1):25:yl(2));
end
set_ylabel(axBot(1),BOTTOM_YDIR);
% panel (c) keeps its own y tick numbers (same ticks as panel b)

% ---- one shared legend for every marker in the figure ----
% Active (RL) uses the same blue filled circle everywhere, so only Heuristic needs an extra key
hp=plot(axA,nan,nan,'^','Color',FIG.cHeur,'MarkerFaceColor',FIG.cHeur,'MarkerSize',5,'LineWidth',FIG.lw-0.4);
lg=legend(axA,[hTop hp],[cLab {'Heuristic'}]);
set(lg,'Orientation','horizontal','Box','off','FontSize',FIG.fs-1,'Location','none','Position',posLeg);
try, lg.ItemTokenSize=[12 10]; catch, end   % shorter legend symbols where supported

% re-apply positions (legend/title creation must not shift the axes)
set(axA,'Position',posTop);
if strcmpi(LAYOUT,'split'), set(axB,'Position',posBL); set(axC,'Position',posBR); else, set(axB,'Position',posBF); end

if FIG.save
    outdir=fullfile(this_dir,FIG.dir); if ~exist(outdir,'dir'), mkdir(outdir); end
    save_png(hf,fullfile(outdir,[FIG.name '.png']),FIG.dpi);
    fprintf('Figure exported to %s\n',fullfile(outdir,[FIG.name '.png']));
end

%% ===================== CHECK AGAINST THE PAPER NUMBERS =====================
fprintf('\nPooled over walking conditions (N=%d), %% reduction vs No-Exo:\n',Ns);
for k=1:4
    fprintf('  %-3s Inactive %6.1f | Active %6.1f (q=%.3f)\n',muscles{k}, ...
        mean(redI(:,k),'omitnan'),mean(redA(:,k),'omitnan'),qA(k));
end
fprintf('%s (N=%d), %% reduction vs No-Exo:\n',COND_H,NsH);
for k=1:4
    fprintf('  %-3s Heuristic %6.1f (q=%.3f) | RL %6.1f (q=%.3f)\n',muscles{k}, ...
        mean(redH(:,k),'omitnan'),qH(k),mean(redRL(:,k),'omitnan'),qRL(k));
end

%% ============================ LOCAL FUNCTIONS ============================
function h=reduction_panel(ax,series,cols,mks,fills,qs,offs,shade,muscles,FIG)
    % Reduction vs No-Exo: participant dots, mean +/- 95% CI, FDR stars.
    % shade=[x0 x1]: light background behind x in [k+x0, k+x1] (marks the 0%/1.2 m/s points).
    axes(ax); hold(ax,'on'); X=1:numel(muscles); h=gobjects(1,numel(series));
    if ~isempty(shade)
        allv=cell2mat(cellfun(@(v) v(:),series(:),'uni',0)); allv=allv(isfinite(allv)); lo=min(allv,[],'omitnan')-50; hi=max(allv,[],'omitnan')+50;
        for k=X
            patch(ax,[k+shade(1) k+shade(2) k+shade(2) k+shade(1)],[lo lo hi hi],[0.92 0.92 0.92], ...
                'EdgeColor','none','HandleVisibility','off');
        end
    end
    yline(ax,0,'-','Color',[0.75 0.75 0.75],'LineWidth',1,'HandleVisibility','off');
    for s=1:numel(series)
        Y=series{s}; m=mean(Y,1,'omitnan'); c=arrayfun(@(k) ci95(Y(:,k)),X);
        for k=X
            jt=(rand(size(Y,1),1)-0.5)*0.06;
            scatter(ax,(k+offs(s))+jt,Y(:,k),FIG.mk*0.25,cols{s},'filled','MarkerFaceAlpha',0.22,'HandleVisibility','off');
        end
        if fills{s}, fc=cols{s}; else, fc='w'; end
        h(s)=errorbar(ax,X+offs(s),m,c,mks{s},'Color',cols{s},'MarkerFaceColor',fc, ...
            'MarkerSize',5,'LineWidth',FIG.lw-0.5,'CapSize',3);
        for k=X
            st=stars(qs{s}(k));
            if ~isempty(st), text(ax,k+offs(s),m(k)+c(k)+4,st,'HorizontalAlignment','center','FontSize',FIG.fs-1); end
        end
    end
    set(ax,'XTick',X,'XTickLabel',muscles); xlim(ax,[0.5 numel(muscles)+0.5]);
    box(ax,'off');
end
function set_ylabel(ax,ydir)
    if strcmpi(ydir,'reverse'), ylabel(ax,{'Reduction vs No-Exo (%)','\downarrow less activity'});
    else, ylabel(ax,'Reduction vs No-Exo (%)'); end
end
function wc=wholecycle(fpath,muscles)
    d=load(fpath,'emg_cycles'); wc=nan(1,4);
    for k=1:4
        X=cell2mat(d.emg_cycles.(muscles{k})');
        wc(k)=mean(X(:),'omitnan');
    end
end
function q=trial_quality(fpath,muscles)
    d=load(fpath,'emg_cycles'); validfrac=nan(1,4); consist=nan(1,4);
    for k=1:4
        X=cell2mat(d.emg_cycles.(muscles{k})');
        good=~all(isnan(X),1) & ~all(X==0 | isnan(X),1);
        Xv=X(:,good); validfrac(k)=size(Xv,2)/max(size(X,2),1);
        if size(Xv,2)>=2
            mu=mean(Xv,2,'omitnan'); Xc=Xv-mean(Xv,1); muc=mu-mean(mu);
            num=sum(Xc.*muc,1); den=sqrt(sum(Xc.^2,1).*sum(muc.^2));
            r=num./den; consist(k)=mean(r(isfinite(r)));
        end
    end
    q=mean(consist,'omitnan')*mean(validfrac,'omitnan');
end
function c=ci95(x)
    x=x(~isnan(x)); n=numel(x); if n<2, c=0; return; end
    c=tcrit95(n-1)*std(x)/sqrt(n);
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
function save_png(h,file,dpi)
    try, exportgraphics(h,file,'Resolution',dpi);
    catch
        set(h,'Units','centimeters'); pp=get(h,'Position');
        set(h,'PaperUnits','centimeters','PaperPositionMode','manual','PaperSize',[pp(3) pp(4)],'PaperPosition',[0 0 pp(3) pp(4)]);
        print(h,file,'-dpng',sprintf('-r%d',dpi));
    end
end
