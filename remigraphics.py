import remi
import math
import threading
import random
import signal
import time
import logging

class GraphicsError(Exception):
    """Generic error class for graphics module exceptions."""
    pass

OBJ_ALREADY_DRAWN = "Object currently drawn"
UNSUPPORTED_METHOD = "Object doesn't support operation"
BAD_OPTION = "Illegal option value"
DEAD_THREAD = "Graphics thread quit unexpectedly"


class Transform:
    """Internal class for 2-D coordinate transformations"""
    def __init__(self, w, h, xlow, ylow, xhigh, yhigh):
        # w, h are width and height of window
        # (xlow,ylow) coordinates of lower-left [raw (0,h-1)]
        # (xhigh,yhigh) coordinates of upper-right [raw (w-1,0)]
        xspan = (xhigh-xlow)
        yspan = (yhigh-ylow)
        self.xbase = xlow
        self.ybase = yhigh
        self.xscale = xspan/float(w-1)
        self.yscale = yspan/float(h-1)
        
    def screen(self,x,y):
        # Returns x,y in screen (actually window) coordinates
        xs = (x-self.xbase) / self.xscale
        ys = (self.ybase-y) / self.yscale
        return int(xs+0.5),int(ys+0.5)
        
    def world(self,xs,ys):
        # Returns xs,ys in world coordinates
        x = xs*self.xscale + self.xbase
        y = self.ybase - ys*self.yscale
        return x,y


cv_glbl_graph_win = threading.Condition()
glbl_remi_root = None
glbl_graph_win = None

class GraphWinRemi(remi.App):
    def __init__(self, *args):
        super(GraphWinRemi, self).__init__(*args)

    def main(self, name='Graphics Window'):

        global glbl_remi_root
        glbl_remi_root = self

        self.width = glbl_graph_win.width
        self.height = glbl_graph_win.height

        self._root = remi.gui.Widget(width=self.width,
                               height=self.height)
        self._root.style['position']='absolute'

        self.svg = remi.gui.Svg(self._root.style['width'],
                           self._root.style['height'])
        self.svg.style['position'] = 'absolute'
        self.svg.style['top'] = '0px'
        self.svg.style['left'] = '0px'
        self._root.append(self.svg)

        self.widg = remi.gui.Widget(width=self._root.style['width'],
                               height=self._root.style['height'])
        self.widg.style['background-color'] = 'transparent'
        self.widg.style['position'] = 'absolute'
        self.widg.style['top'] = '0px'
        self.widg.style['left'] = '0px'
        self._root.append(self.widg)
        
        cv_glbl_graph_win.acquire()
        cv_glbl_graph_win.notify()
        cv_glbl_graph_win.release()

        return self._root


class GraphWin:
    def __init__(self, title="Graphics Window", width=600, height=600, *args):

        global glbl_graph_win
        global cv_glbl_graph_win

        glbl_graph_win = self

        self.foreground = "black"
        self.mouseX = None
        self.mouseY = None
        self.height=height
        self.width=width
        self.closed=True
        self.trans = None
        self.autoflush = True
        self._mouseCallback = None

        self.remi = None

        self.thd = threading.Thread(name='graphics',
                                    target=remi.start,
                                    args=(GraphWinRemi,),
                                    kwargs={'title':title,
                                            'address':'0.0.0.0',
                                            'logging':logging.CRITICAL,
                                            })
        self.thd.setDaemon(True)
        self.thd.start()
        
        cv_glbl_graph_win.acquire()
        while self.isClosed():
            cv_glbl_graph_win.wait()
        cv_glbl_graph_win.release()

    def update():
        """Updates are done by the SVG objects, not the window.."""
        pass

    def __checkOpen(self):
        global glbl_remi_root
        if glbl_remi_root == None:
            self.closed = True
        else:
            self.closed = False
            self.remi = glbl_remi_root

    def setBackground(self, color):
        pass

    def setCoords(self,x1, y1, x2, y2):
        """Set coordinates of window to run from (x1,y1) in the
        lower-left corner to (x2,y2) in the upper-right corner."""
        self.trans = Transform(self.width, self.height, x1, y1, x2, y2)

    def close(self):
        global glbl_graph_win
        if self.closed: return
        if self.thd.is_alive():
#            if glbl_graph_win:
#                glbl_graph_win.close()
            glbl_graph_win = None
            signal.pthread_kill(self.thd.ident, signal.SIGKILL)
        self.closed=True

    def isClosed(self):
        self.__checkOpen()
        return self.closed

    def isOpen(self):
        return not self.closed

    def __autoflush(self):
        pass

    def create_line(self, x1,y1,x2,y2, fill='black'):
        """Draw a line in canvas coordinates"""
        line = remi.gui.SvgLine(x1,y1,x2,y2)
        line.style['color'] = fill
        self.remi.svg.append(line)

    def plot(self, x, y, color="black"):
        """Set pixel (x,y) to the given color"""
        self.__checkOpen()
        xs,ys = self.toScreen(x,y)
        self.create_line(xs,ys,xs+1,ys, fill=color)
        self.__autoflush()

    def plotPixel(self, x, y, color="black"):
        """Set pixel raw (independent of window coordinates) pixel
        (x,y) to color"""
        self.__checkOpen()
        self.create_line(x,y,x+1,y, fill=color)
        self.__autoflush()
      
    def flush(self):
        """Update drawing to the window"""
        self.__checkOpen()
        pass

    def setMouseHandler(self, func):
        self._mouseCallback = func
        
    def _onClickHandler(self, widget, x, y):
        self.mouseX = int(x)
        self.mouseY = int(y)
        if self._mouseCallback:
            self._mouseCallback(Point(x,y))

    def getMouse(self):
        """Wait for mouse click and return Point object representing
        the click"""
        if self.isClosed():
            raise GraphicsError("getMouse in closed window")
            
        self.remi.widg.set_on_mouseup_listener(self._onClickHandler)
        self.mouseX = None
        self.mouseY = None
        while self.mouseX == None or self.mouseY == None:
            if self.isClosed(): raise GraphicsError("getMouse in closed window")
            time.sleep(.05) # give up thread
        x,y = self.toWorld(self.mouseX, self.mouseY)
        self.mouseX = None
        self.mouseY = None
        return Point(x,y)

    def checkMouse(self):
        """Return last mouse click or None if mouse has
        not been clicked since last call"""
        if self.isClosed():
            raise GraphicsError("checkMouse in closed window")
        if self.mouseX != None and self.mouseY != None:
            x,y = self.toWorld(self.mouseX, self.mouseY)
            self.mouseX = None
            self.mouseY = None
            return Point(x,y)
        else:
            return None

    def getHeight(self):
        """Return the height of the window"""
        return self.height
        
    def getWidth(self):
        """Return the width of the window"""
        return self.width
    
    def toScreen(self, x, y):
        trans = self.trans
        if trans:
            return self.trans.screen(x,y)
        else:
            return x,y
                      
    def toWorld(self, x, y):
        trans = self.trans
        if trans:
            return self.trans.world(x,y)
        else:
            return x,y

# Default values for various item configuration options. Only a subset of
#   keys may be present in the configuration dictionary for a given item
DEFAULT_CONFIG = {
      "fill":"",
      "color":"",
      "stroke-width" : 1,
      "outline":"black",
      "arrow":"none",
      "text":"",
      "text-anchor":"middle",
      "font": ("helvetica", 12, "normal"),
      "background-color" : "white"
}

class GraphicsObject:

    """Generic base class for all of the drawable objects"""
    # A subclass of GraphicsObject should override _draw and
    #   and _move methods.
    
    def __init__(self, options):
        # options is a list of strings indicating which options are

        
        # When an object is drawn, canvas is set to the GraphWin(canvas)
        #    object where it is drawn and id is the Remi identifier of the
        #    drawn shape
        self.canvas = None
        self.id = None

        # config is the dictionary of configuration options for the widget.
        config = {}
        for option in options:
            config[option] = DEFAULT_CONFIG[option]
        self.config = config
        
    def setFill(self, color):
        """Set interior color to color"""
        self._reconfig("fill", color)
        
    def setOutline(self, color):
        """Set outline color to color"""
        self._reconfig("outline", color)
        
    def setWidth(self, width):
        """Set line weight to width"""
        self._reconfig("stroke-width", width)

    def draw(self, graphwin):

        """Draw the object in graphwin, which should be a GraphWin
        object.  A GraphicsObject may only be drawn into one
        window. Raises an error if attempt made to draw an object that
        is already visible."""

        if self.canvas and not self.canvas.isClosed(): raise GraphicsError(OBJ_ALREADY_DRAWN)
        if graphwin.isClosed(): raise GraphicsError("Can't draw to closed window")
        self.canvas = graphwin
        if self.id:
            self.id.set_enabled(True)
        else:
            self.id = self._draw(graphwin, self.config)
            self.key = graphwin.remi.svg.append(self.id)
            
    def undraw(self):

        """Undraw the object (i.e. hide it). Returns silently if the
        object is not currently drawn."""
        
        if self.id:
            self.id.set_enabled(False)

    def update(self):
        if self.id:
            self.id.redraw()

    def move(self, dx, dy):

        """move object dx units in x direction and dy units in y
        direction"""

        canvas = self.canvas
        if canvas:
            self.undraw()
        self._move(dx,dy)
        if canvas:
            self.draw(canvas)
           
    def _reconfig(self, option, setting):
        # Internal method for changing configuration of the object
        # Raises an error if the option does not exist in the config
        #    dictionary for this object
        if option not in self.config:
            raise GraphicsError(UNSUPPORTED_METHOD)
        options = self.config
        options[option] = setting

        if self.id:
            if option == 'outline':
                self.id.attributes['stroke'] = setting
            else:
                self.id.attributes[option]=setting
            canvas = self.canvas
            self.update()

    def _draw(self, canvas, options):
        """draws appropriate figure on canvas with options provided
        Returns Tk id of item drawn"""
        pass # must override in subclass


    def _move(self, dx, dy):
        """updates internal state of object to move it dx,dy units"""
        pass # must override in subclass

         
class Point(GraphicsObject):
    def __init__(self, x, y):
        GraphicsObject.__init__(self, ["outline", "fill"])
        self.setFill = self.setOutline
        self.x = x
        self.y = y

    def __str__(self):
        return '(' + str(self.x) + ', ' + str(self.y) + ')'
        
    def _draw(self, canvas, options):
        x,y = canvas.toScreen(self.x,self.y)
        pt = remi.gui.SvgRectangle(int(x), int(y), int(x+1), int(y+1))
        pt.attributes['stroke'] = options['outline']
        return pt
        
    def _move(self, dx, dy):
        self.x = self.x + dx
        self.y = self.y + dy
        
    def clone(self):
        other = Point(self.x,self.y)
        other.config = self.config.copy()
        return other
                
    def getX(self): return self.x
    def getY(self): return self.y

class _BBox(GraphicsObject):
    # Internal base class for objects represented by bounding box
    # (opposite corners) Line segment is a degenerate case.
    
    def __init__(self, p1, p2, options=["outline","fill", "stroke-width"]):
        GraphicsObject.__init__(self, options)
        self.p1 = p1.clone()
        self.p2 = p2.clone()

    def __str__(self):
        return 'Bbox(' + str(self.p1) + ', ' + str(self.p2) + ')'

    def _move(self, dx, dy):
        self.p1.x = self.p1.x + dx
        self.p1.y = self.p1.y + dy
        self.p2.x = self.p2.x + dx
        self.p2.y = self.p2.y  + dy
                
    def getP1(self): return self.p1.clone()

    def getP2(self): return self.p2.clone()
    
    def getCenter(self):
        p1 = self.p1
        p2 = self.p2
        return Point((p1.x+p2.x)/2.0, (p1.y+p2.y)/2.0)
    
class Rectangle(_BBox):
    
    def __init__(self, p1, p2):
        _BBox.__init__(self, p1, p2)
    
    def __str__(self):
        return 'Rect(' + str(self.p1) + ', ' + str(self.p2) + ')'

    def _draw(self, canvas, options):
        p1 = self.p1
        p2 = self.p2
        x1,y1 = canvas.toScreen(p1.x,p1.y)
        x2,y2 = canvas.toScreen(p2.x,p2.y)
        minx, maxx = min(x1,x2), max(x1,x2)
        miny, maxy = min(y1,y2), max(y1,y2)
        w = maxx-minx
        h = maxy-miny
        pt = remi.gui.SvgRectangle(minx, miny, w, h)
        pt.attributes['stroke'] = options['outline']
        if len(options['fill']) > 0:
            pt.attributes['fill'] = options['fill']
        return pt
        
    def clone(self):
        other = Rectangle(self.p1, self.p2)
        other.config = self.config.copy()
        return other

class Oval(_BBox):
    
    def __init__(self, p1, p2):
        _BBox.__init__(self, p1, p2)
        
    def clone(self):
        other = Oval(self.p1, self.p2)
        other.config = self.config.copy()
        return other
   
    def _draw(self, canvas, options):
        p1 = self.p1
        p2 = self.p2
        x1,y1 = canvas.toScreen(p1.x,p1.y)
        x2,y2 = canvas.toScreen(p2.x,p2.y)
        
        lx,mx = min(x1,x2),max(x1,x2)
        ly,my = min(y1,y2),max(y1,y2)
        w,h = mx-lx, my-ly
        rx = w//2
        ry = h//2
        cx = mx + rx
        cy = my + ry
        pt = remi.gui.SvgEllipse(int(cx), int(cy), int(rx), int(ry))
        pt.attributes['stroke'] = options['outline']
        if len(self.config['fill']) > 0: 
            pt.style['color'] = self.config['fill']
        return pt
    
class Circle(Oval):
    def __init__(self, center, radius):
        p1 = Point(center.x-radius, center.y-radius)
        p2 = Point(center.x+radius, center.y+radius)
        Oval.__init__(self, p1, p2)
        self.radius = radius
        
    def clone(self):
        other = Circle(self.getCenter(), self.radius)
        other.config = self.config.copy()
        return other
        
    def getRadius(self):
        return self.radius

class Line(_BBox):
    
    def __init__(self, p1, p2):
        _BBox.__init__(self, p1, p2, ["arrow","fill","width"])
        self.setFill(DEFAULT_CONFIG['outline'])
        self.setOutline = self.setFill
   
    def clone(self):
        other = Line(self.p1, self.p2)
        other.config = self.config.copy()
        return other
  
    def _draw(self, canvas, options):
        p1 = self.p1
        p2 = self.p2
        x1,y1 = canvas.toScreen(p1.x,p1.y)
        x2,y2 = canvas.toScreen(p2.x,p2.y)
        line = remi.gui.SvgLine(int(x1), int(y1), int(x2), int(y2))
        if len(self.config['fill']) > 0: 
            line.style['color'] = self.config['fill']
        return line
        
    def setArrow(self, option):
        if not option in ["first","last","both","none"]:
            raise GraphicsError(BAD_OPTION)
        self._reconfig("arrow", option)

class Text(_BBox):
    
    def __init__(self, p1, text):
        GraphicsObject.__init__(self, ["text-anchor",'color',
                                       "fill","text", "font",
                                       'background-color'])
        self.p1 = p1
        self.setFill(DEFAULT_CONFIG['outline'])
        self.text = text
        self.setOutline = self.setFill
   
    def clone(self):
        other = Text(self.p1, self.text)
        other.config = self.config.copy()
        return other
  
    def _draw(self, canvas, options):
        p1 = self.p1
        x1,y1 = canvas.toScreen(p1.x,p1.y)
        line = remi.gui.SvgText(int(x1), int(y1), self.text)
        line.attributes['text-anchor'] = 'middle'
        if len(self.config['fill']) > 0: 
            line.style['color'] = self.config['fill']
        return line

    def setText(self,text):
        self.text = text
        if self.id:
            self.id.set_text(self.text)
        
    def getText(self):
        return self.text
            
    def getAnchor(self):
        return self.anchor.clone()

    def setFace(self, face):
        if face in ['helvetica','arial','courier','times roman']:
            f,s,b = self.config['font']
            self._reconfig("font",(face,s,b))
        else:
            raise GraphicsError(BAD_OPTION)

    def setSize(self, size):
        if 5 <= size <= 36:
            f,s,b = self.config['font']
            self._reconfig("font", (f,size,b))
        else:
            raise GraphicsError(BAD_OPTION)

    def setStyle(self, style):
        if style in ['bold','normal','italic', 'bold italic']:
            f,s,b = self.config['font']
            self._reconfig("font", (f,s,style))
        else:
            raise GraphicsError(BAD_OPTION)

    def setTextColor(self, color):
        self.setFill(color)


        

class Polygon(GraphicsObject):
    
    def __init__(self, *points):
        # if points passed as a list, extract it
        if len(points) == 1 and type(points[0]) == type([]):
            points = points[0]
        self.points = list(map(Point.clone, points))
        GraphicsObject.__init__(self, ["outline", "width", "fill"])
        
    def clone(self):
        other = Polygon(*self.points)
        other.config = self.config.copy()
        return other

    def getPoints(self):
        return list(map(Point.clone, self.points))

    def _move(self, dx, dy):
        for p in self.points:
            p.move(dx,dy)
   
    def _draw(self, canvas, options):
        args = [canvas]
        pl = remi.gui.SvgPolyline()

        for p in self.points:
            x,y = canvas.toScreen(p.x,p.y)
            pl.add_coord(int(x), int(y))
            
        if len(self.config['fill']) > 0: 
            pl.style['color'] = self.config['fill']

        return pl

class TextBox(GraphicsObject):
    
    def __init__(self, p, text, width=0):
        GraphicsObject.__init__(self, ["text-anchor",'color',
                                       "fill","text", "font",
                                       'background-color'])
        self.setText(text)
        self.width=width
        self.anchor = p.clone()
        self.setFill(DEFAULT_CONFIG['outline'])
        self.config['text-anchor']='middle'
        self.config['background-color'] = 'transparent'
        self.setOutline = self.setFill
        
    def draw(self, graphwin):

        """Draw the object in graphwin, which should be a GraphWin
        object.  A GraphicsObject may only be drawn into one
        window. Raises an error if attempt made to draw an object that
        is already visible."""

        if self.canvas and not self.canvas.isClosed(): raise GraphicsError(OBJ_ALREADY_DRAWN)
        if graphwin.isClosed(): raise GraphicsError("Can't draw to closed window")
        self.canvas = graphwin
        if self.id:
            self.id.set_enabled(True)
        else:
            self.id = self._draw(graphwin, self.config)
            self.key = graphwin.remi.widg.append(self.id)
            
    def undraw(self):

        """Undraw the object (i.e. hide it). Returns silently if the
        object is not currently drawn."""
        
        if self.id:
            self.id.set_enabled(False)

    def _draw(self, canvas, options):
        p = self.anchor
        x,y = canvas.toScreen(p.x,p.y)
        txt = remi.gui.Label(self.text)
        if len(self.config['fill']) > 0: 
            txt.style['color'] = self.config['fill']
        f,s,b=self.config['font']
        txt.style['font-family'] = f
        txt.style['font-weight'] = b
        txt.style['text-align'] = 'center'
        txt.style['background-color'] = 'transparent'
        txt.style['position'] = 'absolute'
        txt.style['top'] = str(int(y)) + "px"
        txt.style['left'] = str(int(x)) + "px"

        return txt
        
    def _reconfig(self, option, setting):
        # Internal method for changing configuration of the object
        # Raises an error if the option does not exist in the config
        #    dictionary for this object
        if option not in self.config:
            raise GraphicsError(UNSUPPORTED_METHOD)
        options = self.config
        options[option] = setting

        if self.id:
            if option == 'outline':
                self.id.style['stroke'] = setting
            else:
                self.id.style[option]=setting
            self.id.redraw()

    def _move(self, dx, dy):
        self.anchor.move(dx,dy)
        
    def clone(self):
        other = Text(self.anchor, self.text)
        other.config = self.config.copy()
        return other

    def setText(self,text):
        self.text = text
        if self.id:
            self.id.set_text(self.text)
        
    def getText(self):
        return self.text
            
    def getAnchor(self):
        return self.anchor.clone()

    def setFace(self, face):
        if face in ['helvetica','arial','courier','times roman']:
            f,s,b = self.config['font']
            self._reconfig("font",(face,s,b))
        else:
            raise GraphicsError(BAD_OPTION)

    def setSize(self, size):
        if 5 <= size <= 36:
            f,s,b = self.config['font']
            self._reconfig("font", (f,size,b))
        else:
            raise GraphicsError(BAD_OPTION)

    def setStyle(self, style):
        if style in ['bold','normal','italic', 'bold italic']:
            f,s,b = self.config['font']
            self._reconfig("font", (f,s,style))
        else:
            raise GraphicsError(BAD_OPTION)

    def setTextColor(self, color):
        self.setFill(color)

class Entry(Text):

    def __init__(self, p, width):
        Text.__init__(self, p, "")
        self.width = width
        self.text = ""
        self.config['background-color'] = 'lightgray'
        self.font = DEFAULT_CONFIG['font']


    def _ontextchange(self, widget, text):
        self.text = widget.get_text()

    def _draw(self, canvas, options):
        p = self.anchor
        x,y = canvas.toScreen(p.x,p.y)
        frm = remi.gui.TextInput(width=self.width)
        self.setText(self.text)
        frm.style['position'] = 'absolute'
        frm.style['top'] = str(int(y)) + "px"
        frm.style['left'] = str(int(x)) + "px"
        frm.set_on_change_listener(self._ontextchange)

        if len(self.config['color']) > 0: 
            frm.style['color'] = self.config['color']

        return frm

def main():
    win = GraphWin("My Circle", 100, 100)
    c = Circle(Point(50,50), 10)
    c.draw(win)
    win.getMouse() # Pause to view result
    win.close()    # Close window when done

if __name__ == '__main__':
    main()
