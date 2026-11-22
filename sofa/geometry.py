"""Procedural display geometry, in metres. These meshes are schematic visuals."""
import math


def merge(meshes):
    points, triangles = [], []
    for vertices, faces in meshes:
        offset = len(points)
        points.extend(vertices)
        triangles.extend([[i+offset for i in f] for f in faces])
    return points, triangles


def box(center, size):
    points = [[center[0]+sx*size[0]/2,center[1]+sy*size[1]/2,center[2]+sz*size[2]/2]
              for sx,sy,sz in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
                               (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
    faces = [[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],
             [3,7,6],[3,6,2],[0,4,7],[0,7,3],[1,2,6],[1,6,5]]
    return points, faces


def tube_x(x, width, radius, thickness, n=24):
    points=[]
    for r in (radius, radius-thickness):
        for xx in (x-width/2,x+width/2):
            points += [[xx,r*math.cos(2*math.pi*i/n),r*math.sin(2*math.pi*i/n)] for i in range(n)]
    triangles=[]
    for i in range(n):
        j=(i+1)%n
        for a,b,c,d in [(i,j,n+j,n+i),(2*n+i,3*n+i,3*n+j,2*n+j),
                         (i,2*n+i,2*n+j,j),(n+i,n+j,3*n+j,3*n+i)]:
            triangles += [[a,b,c],[a,c,d]]
    return points, triangles


def ellipsoid(center, radii, n=16, m=8):
    # Separate poles avoid zero-area triangles in the display mesh.
    points=[[center[0],center[1],center[2]+radii[2]]]
    for j in range(1,m):
        theta=math.pi*j/m
        points += [[center[0]+radii[0]*math.sin(theta)*math.cos(2*math.pi*i/n),
                    center[1]+radii[1]*math.sin(theta)*math.sin(2*math.pi*i/n),
                    center[2]+radii[2]*math.cos(theta)] for i in range(n)]
    bottom=len(points); points.append([center[0],center[1],center[2]-radii[2]])
    triangles=[]
    for i in range(n):
        j=(i+1)%n
        triangles += [[0,1+i,1+j],[bottom,1+(m-2)*n+j,1+(m-2)*n+i]]
    for ring in range(m-2):
        for i in range(n):
            j=(i+1)%n;a=1+ring*n+i;b=1+ring*n+j;c=b+n;d=a+n
            triangles += [[a,d,c],[a,c,b]]
    return points,triangles


def rotate(points, angle):
    c,s=math.cos(angle),math.sin(angle)
    return [[c*x+s*y,-s*x+c*y,z] for x,y,z in points]


class SuitGeometry:
    COLORS = {"limb":[0.64,0.67,0.72,0.4],"fabric":[0.09,0.10,0.13,1],
              "cuffs":[0.05,0.18,0.9,1],"housings":[1,0.20,0.025,1],
              "metal":[0.65,0.68,0.72,1],"flexion":[0.13,0.48,0.95,1],
              "extension":[0.95,0.40,0.12,1]}

    def __init__(self,length):
        self.length=length
        self.fixed={"limb":ellipsoid([-.24,0,0],[.25,.06,.065]),
                    "fabric":box([-.21,0,.07],[.40,.035,.013]),
                    "metal":box([-.10,0,.08],[.20,.022,.012])}
        self.moving={"limb":ellipsoid([length/2,0,0],[length/2,.052,.055]),
                     "fabric":box([length/2,0,.065],[length-.025,.035,.013]),
                     "metal":box([.10,0,.08],[.20,.022,.012])}
        for name,model in (("fixed",self.fixed),("moving",self.moving)):
            sign=-1 if name=="fixed" else 1
            locations=[sign*.12,sign*min(.32,length-.04)]
            model["cuffs"]=merge([tube_x(x,.024,.073,.008) for x in locations])
            model["housings"]=merge([box([x,0,.079],[.044,.045,.025]) for x in locations])
        self.hinge=ellipsoid([0,0,.084],[.044,.029,.015])

    def bank(self,side,angle,pressure,maximum):
        start=[-.15,side*.066,0]
        end=rotate([[.15,side*.066,0]],angle)[0]
        fraction=max(0,min(1,pressure/maximum))
        middle=[(start[0]+end[0])/2+side*.035*math.sin(angle/2),
                (start[1]+end[1])/2+side*(.05+.015*fraction)*math.cos(angle/2),0]
        bags=[]
        for i in range(7):
            t=(i+.5)/7;u=1-t
            center=[u*u*start[k]+2*u*t*middle[k]+t*t*end[k] for k in range(3)]
            bags.append(ellipsoid(center,[.024,.012+.009*fraction,.026+.009*fraction],n=12,m=6))
        return merge(bags)

    def meshes(self,angle,flexion_psi,extension_psi,maximum):
        out={}
        for name in self.COLORS:
            pieces=[]
            if name in self.fixed:pieces.append(self.fixed[name])
            if name in self.moving:
                points,faces=self.moving[name];pieces.append((rotate(points,angle),faces))
            if name=="fabric":pieces.append(self.hinge)
            if pieces:out[name]=merge(pieces)
        out["flexion"]=self.bank(-1,angle,flexion_psi,maximum)
        out["extension"]=self.bank(1,angle,extension_psi,maximum)
        return out
