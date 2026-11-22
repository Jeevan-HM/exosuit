"""Separate, illustrative FEM chamber test, with genuine pressure traction.

This tests an assumed hollow rectangular specimen, not the photographed
fabric assembly. It is not mechanically coupled to knee_exosuit.py.
"""
import math
from pathlib import Path
import sys
BASE=Path(__file__).resolve().parent
if str(BASE) not in sys.path:sys.path.insert(0,str(BASE))
import Sofa
from chamber_mesh import generate_chamber
from units import clamp, finite, psi_to_pa


class ChamberController(Sofa.Core.Controller):
    def __init__(self,root,pressure):
        super().__init__(name="ChamberPressure_PSI")
        self.root,self.pressure=root,pressure
        self.addData("targetPsi",type="double",value=0.,group="Inputs (PSI)",help="Illustrative test input, not a hardware rating")
        self.addData("maximumPsi",type="double",value=10.,group="Inputs (PSI)")
        self.addData("pressureLagSeconds",type="double",value=.25,group="Inputs (PSI)")
        self.addData("measuredPsi",type="double",value=0.,group="Telemetry")
        self.addData("status",type="string",value="Set targetPsi, then press SOFA Play",group="Telemetry")
        self.actual=0.;self.last_time=-1.

    def onAnimateBeginEvent(self,event):
        t,dt=float(self.root.time.value),float(self.root.dt.value)
        if t<self.last_time-1e-10 or (t<=1e-12 and self.last_time>=0):self.actual=0.
        self.last_time=t
        try:
            maximum=finite(self.maximumPsi.value);lag=finite(self.pressureLagSeconds.value)
            if maximum<=0 or maximum>20 or lag<=0:raise ValueError("Use 0 < maximumPsi <= 20 and a positive pressure lag")
            target=clamp(finite(self.targetPsi.value),0,maximum)
            self.status.value="Illustrative FEM specimen; all geometry and material parameters assumed"
        except (ValueError,TypeError) as error:
            target=0.;lag=.25;self.status.value="Venting: "+str(error)
        self.actual+=(target-self.actual)*(1-math.exp(-dt/lag))
        self.measuredPsi.value=self.actual
        # SI model: mesh coordinates in m, stiffness in Pa, traction in Pa.
        self.pressure.pressure.value=psi_to_pa(self.actual)

    def onKeypressedEvent(self,event):
        key=str(event.get("key","")).upper()
        if key in ("+","="):self.targetPsi.value=min(float(self.maximumPsi.value),float(self.targetPsi.value)+.5)
        elif key=="-":self.targetPsi.value=max(0,float(self.targetPsi.value)-.5)
        elif key=="0":self.targetPsi.value=0.


def createScene(root,visuals=True):
    plugins=["Sofa.Component.AnimationLoop","Sofa.Component.ODESolver.Backward",
             "Sofa.Component.LinearSolver.Iterative","Sofa.Component.StateContainer",
             "Sofa.Component.Mass","Sofa.Component.Topology.Container.Dynamic",
             "Sofa.Component.Constraint.Projective","Sofa.Component.SolidMechanics.FEM.Elastic",
             "Sofa.Component.MechanicalLoad","Sofa.Component.Mapping.Linear"]
    if visuals:plugins += ["Sofa.Component.Visual","Sofa.GL.Component.Rendering3D"]
    root.addObject("RequiredPlugin",pluginName=plugins)
    root.dt=1/600;root.gravity=[0,0,0];root.animate=False
    root.addObject("DefaultAnimationLoop")
    mesh=generate_chamber()
    body=root.addChild("IllustrativeChamber_FEM")
    body.addObject("EulerImplicitSolver",name="integrator",rayleighMass=.05,rayleighStiffness=.01)
    body.addObject("CGLinearSolver",iterations=150,tolerance=1e-10,threshold=1e-12)
    body.addObject("TetrahedronSetTopologyContainer",name="volume",position=mesh["positions"],tetrahedra=mesh["tetrahedra"])
    body.addObject("MechanicalObject",name="dofs",template="Vec3d",position=mesh["positions"])
    body.addObject("UniformMass",totalMass=.08)
    body.addObject("TetrahedronFEMForceField",name="elasticity",method="large",poissonRatio=.30,youngModulus=mesh["young_modulus_pa"])
    body.addObject("FixedProjectiveConstraint",indices=mesh["fixed_indices"])
    cavity=body.addChild("ClosedCavity")
    cavity.addObject("TriangleSetTopologyContainer",name="surface",position=mesh["cavity_positions"],triangles=mesh["cavity_triangles"])
    cavity.addObject("MechanicalObject",name="dofs",template="Vec3d",position=mesh["cavity_positions"])
    pressure=cavity.addObject("SurfacePressureForceField",name="tractionPa",template="Vec3d",
                              pressure=0.,useTangentStiffness=False)
    cavity.addObject("BarycentricMapping",input="@../dofs",output="@dofs",mapForces=True,mapMasses=False)
    if visuals:
        root.addObject("VisualStyle",displayFlags="showVisualModels hideBehaviorModels hideForceFields")
        root.addObject("DefaultVisualManagerLoop")
        root.addObject("BackgroundSetting",color=[.065,.075,.095])
        root.addObject("InteractiveCamera",position=[.30,.18,.35],lookAt=[.1,0,0],zNear=.001,zFar=10)
        skin=body.addChild("Skin")
        skin.addObject("OglModel",name="surface",position=mesh["positions"],triangles=mesh["outer_triangles"],color=[.12,.22,.55,1])
        skin.addObject("BarycentricMapping",input="@../dofs",output="@surface",mapForces=False,mapMasses=False)
    root.addObject(ChamberController(root,pressure))
    return root
