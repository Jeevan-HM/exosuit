"""Photo-inspired wearable geometry following actual femur/tibia poses.

These rendering geoms never generate contact or infer mass. The separate
mechanics module adds explicit device inertias to the articulated human.
Pouch swelling is illustrative and uses actual modeled gauge pressure (PSI).
"""
from dataclasses import dataclass
import math
import numpy as np
import mujoco

BLUE=np.array([.045,.16,.85,1.])
RED=np.array([1.,.17,.035,1.])
FABRIC=np.array([.055,.065,.085,1.])
METAL=np.array([.65,.70,.74,1.])
SEAM=np.array([.48,.52,.56,1.])
TUBE=np.array([.66,.86,.87,.85])


@dataclass
class ExosuitGeometry:
    thigh_radius_m:float=.080
    shank_radius_m:float=.065
    cuff_width_m:float=.028
    vented_pouch_thickness_m:float=.008
    inflated_pouch_thickness_m:float=.025
    display_pressure_psi:float=30.

    def validate(self):
        for key,value in vars(self).items():
            if not math.isfinite(value) or value<=0:raise ValueError(f'{key} must be finite and positive')
        if self.inflated_pouch_thickness_m<self.vented_pouch_thickness_m:
            raise ValueError('Inflated pouch thickness must be at least vented thickness')


class ExosuitVisuals:
    """Append wearable geoms to viewer.user_scn or Renderer.scene."""
    def __init__(self,geometry=None):
        self.config=geometry or ExosuitGeometry();self.config.validate()
        self.visible=True;self.last_geometry_count=0

    @staticmethod
    def point(data,body,local):
        b=data.body(body)
        return b.xpos+b.xmat.reshape(3,3)@np.asarray(local,dtype=float)

    def _geom(self,scene,kind,size,pos,mat,color):
        if scene.ngeom>=scene.maxgeom:raise RuntimeError('Exosuit rendering scene is full')
        g=scene.geoms[scene.ngeom]
        mujoco.mjv_initGeom(g,kind,np.asarray(size,dtype=float),np.asarray(pos,dtype=float),
                           np.asarray(mat,dtype=float).reshape(9),np.asarray(color,dtype=float))
        g.specular=.25;g.shininess=.35
        scene.ngeom+=1
        return g

    def _line(self,scene,a,b,radius,color):
        g=self._geom(scene,mujoco.mjtGeom.mjGEOM_CAPSULE,[radius,1,0],
                     np.zeros(3),np.eye(3),color)
        mujoco.mjv_connector(g,mujoco.mjtGeom.mjGEOM_CAPSULE,radius,
                            np.asarray(a,dtype=float),np.asarray(b,dtype=float))

    def _local(self,scene,data,body,kind,size,pos,color,rotation=None):
        r=data.body(body).xmat.reshape(3,3)
        return self._geom(scene,kind,size,self.point(data,body,pos),
                          r if rotation is None else r@rotation,color)

    def _ring(self,scene,data,body,y,radius,width,color,thickness=.005):
        for i in range(24):
            theta=2*math.pi*(i+.5)/24
            c,s=math.cos(theta),math.sin(theta)
            radial=np.array([c,0,s]);tangent=np.array([-s,0,c])
            rotation=np.column_stack((radial,[0,1,0],tangent))
            self._local(scene,data,body,mujoco.mjtGeom.mjGEOM_BOX,
                        [thickness,width/2,math.pi*radius/24+.0005],
                        [radius*c,y,radius*s],color,rotation)

    def _cuff(self,scene,data,body,y,radius):
        c=self.config
        self._ring(scene,data,body,y,radius,c.cuff_width_m,BLUE)
        self._local(scene,data,body,mujoco.mjtGeom.mjGEOM_BOX,
                    [.030,.025,.008],[0,y,-radius-.008],RED)
        self._local(scene,data,body,mujoco.mjtGeom.mjGEOM_CYLINDER,
                    [.020,.009,0],[0,y,-radius-.024],BLUE)
        for k in range(12):
            t=2*math.pi*k/12
            self._local(scene,data,body,mujoco.mjtGeom.mjGEOM_SPHERE,
                        [.0026,0,0],[.019*math.cos(t),y+.019*math.sin(t),-radius-.025],BLUE)
        self._local(scene,data,body,mujoco.mjtGeom.mjGEOM_CYLINDER,
                    [.0045,.010,0],[0,y,-radius-.030],METAL)

    def _sleeve(self,scene,data,body,ys,radius):
        # Narrow dark panels around the limb leave the central knee open.
        middle=.5*sum(ys);half=.5*abs(ys[1]-ys[0])
        for i in range(12):
            t=2*math.pi*(i+.5)/12;c,s=math.cos(t),math.sin(t)
            r=np.column_stack(([c,0,s],[0,1,0],[-s,0,c]))
            self._local(scene,data,body,mujoco.mjtGeom.mjGEOM_BOX,
                        [.0035,half,math.pi*radius/12+.001],
                        [radius*c,middle,radius*s],FABRIC,r)
        for y in ys:
            self._ring(scene,data,body,y,radius+.002,.002,SEAM,thickness=.002)

    def _pouches(self,scene,data,bank,pressure):
        cfg=self.config
        fraction=float(np.clip(pressure/cfg.display_pressure_psi,0,1))
        thickness=cfg.vented_pouch_thickness_m+fraction*(cfg.inflated_pouch_thickness_m-cfg.vented_pouch_thickness_m)
        # Both banks are schematic functional groups, not an inferred air-line map.
        sign=-1 if bank=='extension' else 1
        for z in (-.045,.035):
            a=self.point(data,'femur_l',[sign*.078,-.30,z])
            b=self.point(data,'tibia_l',[sign*.070,-.135,z])
            knee=self.point(data,'tibia_l',[sign*.105,0,z])
            for k in range(5):
                u=(k+.5)/5
                center=(1-u)**2*a+2*(1-u)*u*knee+u*u*b
                tangent=2*(1-u)*(knee-a)+2*u*(b-knee)
                long=tangent/max(np.linalg.norm(tangent),1e-12)
                lateral=data.body('tibia_l').xmat.reshape(3,3)[:,2]
                radial=np.cross(long,lateral);radial/=max(np.linalg.norm(radial),1e-12)
                lateral=np.cross(radial,long)
                rotation=np.column_stack((radial,long,lateral))
                half_length=max(.018,np.linalg.norm(b-a)/9)
                shade=FABRIC.copy();shade[:3]+=(np.array([.01,.12,.09]) if bank=='extension' else np.array([.18,.07,.01]))*fraction
                self._geom(scene,mujoco.mjtGeom.mjGEOM_ELLIPSOID,
                           [thickness,half_length,.024],center,rotation,shade)
                # A pale stitched edge makes separated fabric lobes readable.
                self._line(scene,center-long*half_length+radial*thickness,
                           center+long*half_length+radial*thickness,.0009,SEAM)

    def draw(self,scene,model,data,telemetry=None,clear=False):
        if clear:scene.ngeom=0
        start=scene.ngeom
        if not self.visible:self.last_geometry_count=0;return
        t=telemetry or {}
        cfg=self.config
        for body,ys,radius in [('femur_l',(-.145,-.300),cfg.thigh_radius_m),
                               ('tibia_l',(-.090,-.250),cfg.shank_radius_m)]:
            self._sleeve(scene,data,body,(ys[0]+.035,ys[1]-.030),radius-.004)
            for y in ys:self._cuff(scene,data,body,y,radius)
        knee=self.point(data,'tibia_l',[0,0,-.105])
        top=self.point(data,'femur_l',[0,-.17,-.105])
        lower=self.point(data,'tibia_l',[0,-.25,-.105])
        self._line(scene,top,knee,.012,FABRIC)
        self._line(scene,knee,lower,.012,FABRIC)
        for body,a,b in [('femur_l',[.018,-.29,-.108],[.018,-.36,-.108]),
                          ('tibia_l',[.018,-.035,-.108],[.018,-.105,-.108])]:
            self._line(scene,self.point(data,body,a),self.point(data,body,b),.008,METAL)
        self._local(scene,data,'tibia_l',mujoco.mjtGeom.mjGEOM_CYLINDER,
                    [.027,.012,0],[0,0,-.105],FABRIC)
        self._local(scene,data,'tibia_l',mujoco.mjtGeom.mjGEOM_CYLINDER,
                    [.006,.014,0],[0,0,-.109],METAL)
        self._pouches(scene,data,'extension',t.get('extension_pressure_psi',0.))
        self._pouches(scene,data,'flexion',t.get('flexion_pressure_psi',0.))
        # Soft tubing follows transformed anchors; it is not a force-transmitting cable.
        anchors=[self.point(data,'femur_l',[-.09,-.17,-.04]),
                 self.point(data,'femur_l',[-.12,-.24,-.09]),
                 self.point(data,'tibia_l',[-.12,-.035,-.10]),
                 self.point(data,'tibia_l',[-.08,-.15,-.055])]
        for a,b in zip(anchors[:-1],anchors[1:]):self._line(scene,a,b,.0025,TUBE)
        for body,pos in [('femur_l',[-.09,-.17,-.04]),('tibia_l',[-.08,-.15,-.055])]:
            self._local(scene,data,body,mujoco.mjtGeom.mjGEOM_SPHERE,[.007,0,0],pos,METAL)
        self.last_geometry_count=scene.ngeom-start


def visuals_from_config(config):
    device=config.get('exosuit',{})
    return ExosuitVisuals(ExosuitGeometry(**device.get('geometry',{})))


def configure_rendering(model):
    """Light the dark textile clearly without changing any physical parameter."""
    model.vis.headlight.ambient[:]=[.38,.38,.38]
    model.vis.headlight.diffuse[:]=[.40,.40,.40]
    terrain=model.geom('terrain').id
    model.geom_matid[terrain]=-1
    model.geom_rgba[terrain]=[.55,.57,.60,1.]
