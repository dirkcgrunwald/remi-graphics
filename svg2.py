import remi.gui as gui
from remi import start, App
import math
from threading import Timer
import random

class MyApp(App):
    def __init__(self, *args):
        super(MyApp, self).__init__(*args)

    def on_text_area_change(self, widget, newValue):
        self.lbl.set_text('Text Area value changed!')

    def on_change(self, widget, lbl):
        self.lbl.set_text(widget.get_text())

    def on_click(self, widget):
        self.lbl.set_text('click!')

    def main(self, name='world'):
        self.root = gui.Widget(width=600, height=600, margin='0px auto')
        self.root.style['position']='absolute'

        self.svg = gui.Svg(self.root.style['width'], self.root.style['height'])
        self.svg.style['position'] = 'absolute'
        self.svg.style['top'] = '0px'
        self.svg.style['left'] = '0px'
        self.root.append(self.svg)

        self.widg = gui.Widget(width=self.root.style['width'],
                               height=self.root.style['height'])
        self.widg.style['position'] = 'absolute'
        self.widg.style['top'] = '0px'
        self.widg.style['left'] = '0px'
#        self.root.append(self.widg)

        self.rect = gui.SvgRectangle(0, 0, 
                    self.svg.style['width'], self.svg.style['height'])
        self.rect.set_fill(color='lightgray')
        self.svg.append(self.rect)

        self.circle = gui.SvgCircle(100, 100, 50)
        self.circle.set_position(150,150)
        self.circle.set_fill('gray')
        self.circle.set_stroke(1,'black')
#        self.circle.set_coords(20,20,100,100)
        self.circle.set_on_click_listener(self.on_click)
        self.svg.append(self.circle)

        self.line = gui.SvgLine(0,0,50,100)
        self.svg.append(self.line)

        self.lbl = gui.Label('This is a LABEL!', width=50, height=30, margin='10px')
        #        self.lbl.set_coords(10,50, 200, 30)'
        self.lbl.style['position'] = 'absolute'
        self.lbl.style['top'] = '40px'
        self.lbl.style['left'] = '10px'
        self.root.append(self.lbl)

        self.txt = gui.TextInput(width=200, height=30, margin='10px')
        self.txt.set_text('Change me!')
        #        self.txt.set_coords(10,50, 200, 30)'
        self.txt.set_on_change_listener(self.on_change)
        self.txt.style['position'] = 'absolute'
        self.txt.style['top'] = '200px'
        self.txt.style['left'] = '100px'
        self.root.append(self.txt)


        return self.root

if __name__ == "__main__":
    start(MyApp, address='0.0.0.0')

