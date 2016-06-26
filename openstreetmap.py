#!/usr/bin/env python
# coding=utf-8
#
# Author: Patrick Salecker <mail@salecker.org>

"""
Functions for drawing a map with Openstreetmap tiles as background
"""

import math
import random
import urllib
import os
import sys
import cairo
import time

from threading import Thread

class Openstreetmap:
	def __init__(self, link=False, ctx=False):
		if link is False:
			#link="http://tah.openstreetmap.org/Tiles/tile/%i/%i/%i.png"
			link="http://tile.openstreetmap.org/%i/%i/%i.png"
		self.cachedir=os.path.expanduser("~")+os.sep+".osmcache"
		self.cachetime=60*60*24*7*2 # two weeks in seconds
		self.cache_hit = 0.0
		self.cache_fail = 0.0
		self.link=link
		self.ctx=ctx
		
		self.xmin=None
		self.xmax=None
		self.ymin=None
		self.ymax=None
		self.zoom=None
		
		self.lat={"min":None,"max":None,"center":None}
		self.lon={"min":None,"max":None,"center":None}
		
		self.threading=False
		self.download_finish=False
		
		self.no_dupes=False
		self.used_points={}
		
	def activate_threading(self):
		"""Use another thread to download the tiles
		"""
		self.threading=True
		
	def createcontext(self):
		"""Create a cairo surface and a context in it
		"""
		self.surface=cairo.ImageSurface (cairo.FORMAT_ARGB32, self.width, self.height)
		self.ctx=cairo.Context(self.surface)
		self.used_points={}
		
	def setarea(self,xmin,xmax,ymin,ymax,zoom):
		"""Set the area of the map and calculate all necessary values
		"""
		if xmin!=self.xmin or xmax!=self.xmax or ymin!=self.ymin or ymax!=self.ymax or zoom!=self.zoom:
			self.xmin=xmin
			self.xmax=xmax
			self.ymin=ymin
			self.ymax=ymax
			self.zoom=zoom
			self.n = 2.0 ** self. zoom
			
			degmin=self.num2deg(xmin, ymax+1, zoom)
			self.lat["min"]=degmin[0]
			self.lon["min"]=degmin[1]
		
			degmax=self.num2deg(xmax+1, ymin, zoom)
			self.lat["max"]=degmax[0]
			self.lon["max"]=degmax[1]
			
			xcenter=(xmin+xmax+1)/2
			ycenter=(ymin+ymax+1)/2
			
			if (xmax-xmin)%2==0:
				xcenter+=0.5
			if (ymax-ymin)%2==0:
				ycenter+=0.5
				
			"""print xmin,ymin
			print xcenter,ycenter
			print xmax,ymax"""
			
			degcenter=self.num2deg(xcenter, ycenter, zoom)
			self.lat["center"]=degcenter[0]
			self.lon["center"]=degcenter[1]
			
			self.width=(xmax-xmin+1)*256
			self.height=(ymax-ymin+1)*256
			
			return True
			
		else:
			return False
			
	def setarea_position(self,lat,lon,xsize,ysize,zoom):
		"""Calculate the area from a coordinate and the size
		"""
		x,y=self.deg2num(lat,lon,zoom)

		if xsize%2==0:
			if int(x)==round(x):	
				xmin=int(x)-(xsize/2)#
				xmax=int(x)+(xsize/2)-1#
			else:
				xmin=int(x)-(xsize/2)+1#
				xmax=int(x)+(xsize/2)#
		else:
			xmin=int(x)-((xsize-1)/2)#
			xmax=int(x)+((xsize-1)/2)#
			
		if ysize%2==0:
			if int(y)==round(y):
				ymin=int(y)-(ysize/2)#
				ymax=int(y)+(ysize/2)-1#
			else:
				ymin=int(y)-(ysize/2)+1#
				ymax=int(y)+(ysize/2)#
		else:
			ymin=int(y)-((ysize-1)/2)#
			ymax=int(y)+((ysize-1)/2)#
			
		return self.setarea(int(xmin),int(xmax),int(ymin),int(ymax),int(zoom))
		
	def buildmap(self):
		"""Load the tiles and draw them in the context
		"""
		if self.threading is True:
			self.dlthread=DownloadThread(self.download_result)
		#print "Build ground map..."
		self.fill_background((255,255,255))
		for y in range(self.ymin,self.ymax+1):
			for x in range(self.xmin,self.xmax+1):
				path=self.gettile(x,y)
				if path is not False:
					try:
						tile=cairo.ImageSurface.create_from_png(path)			
						self.ctx.set_source_surface (tile, (x-self.xmin)*256, (y-self.ymin)*256)
						self.ctx.paint()
					except:
						continue
		self.ctx.paint()
		
		#print 100.0 / (self.cache_hit + self.cache_fail) * self.cache_hit, "%"
		
		if self.threading is True:
			self.dlthread.start()
		
	def saveimage(self, filename):
		"""Write image to PNG file
		"""
		if "surface" in dir(self):
			self.surface.write_to_png (filename)
			#print "save"
		else:
			return False
	
	def gettile(self,x,y):
		"""Load tile and return path
		"""
		tilelink = self.link % (self.zoom,x,y)
		old=False
		loadtile=False
		tilepath="%s%s%i%s%i%s%i.png" % (self.cachedir,os.sep,self.zoom,os.sep,x,os.sep,y)
		tiledir=tilepath.rsplit(os.sep,1)[0]
		if not os.path.isdir(tiledir):
			os.makedirs(tiledir)
		if os.path.isfile(tilepath):
			age=int(time.time()-os.stat(tilepath)[8])
			if age>self.cachetime:
				old=True
				if self.threading is True:
					print "Tile %s,%s,%s %s days old, reloading" %(self.zoom,x,y,age/60/60/24)
					self.dlthread.queue.append((self.zoom,x,y))
				else:
					loadtile=True
		if not os.path.isfile(tilepath):
			loadtile=True
		if loadtile is True:
			if self.threading is True:
				self.dlthread.queue.append((self.zoom,x,y))
				if old is True:
					return True
				else:
					return False
			else:
				try:
					#print ".",
					self.cache_fail += 1
					urllib.urlretrieve(tilelink, tilepath)
					time.sleep(0.1)
				except IOError:
					return False
		else:
			self.cache_hit += 1
		
		return tilepath	
		
	def download_result(self,answer):
		self.download_finish=True
	
	def chose_color(self,color):
		"""Return a RGB color
		"""
		if color=="last":
			r,g,b=self.lastcolor
		elif type(color) == tuple or type(color) == list:
			r,g,b=color
		else:
			r=random.random()
			g=random.random()
			b=random.random()
		
		return r,g,b
		
	def fill_background(self,color):
		"""Fill the background of the context
		"""
		r,g,b=color
		self.ctx.set_source_rgb(r,g,b)
		self.ctx.rectangle(0, 0, self.width, self.height)
		self.ctx.fill()
		self.ctx.stroke()
		
	def draw_no_dupes(self):
		self.no_dupes=True
		
	def is_point_used(self,x,y):
		if x in self.used_points:
			if y in self.used_points[x]:
				return True
			else:
				self.used_points[x][y]=True
				return False
		else:
			self.used_points[x]={y: True}
			return False
	
	def add_arc(self,lat,lon,size,color="random",fill=True,border=False):
		"""Add an arc to the context
		"""
		xrel,yrel=self.deg2num_rel(lat, lon)
		self.add_arc_xy(xrel, yrel, size, color, fill, border)
		
	def add_arc_xy(self, xrel, yrel, size, color="random", fill=True, border=False):
		if self.no_dupes is True and self.is_point_used(xrel,yrel):
			return
		
		#self.ctx.push_group()
		self.ctx.arc(xrel, yrel, size, 0, 360)
		
		r,g,b=self.chose_color(color)
		self.ctx.set_source_rgba(r,g,b, 0.5)
		#self.lastcolor=r,g,b
		if fill:
			self.ctx.fill()
		else:
			self.ctx.set_line_width(1)
		self.ctx.stroke()
		
		if border:
			self.ctx.set_line_width(1)
			self.ctx.set_source_rgba(0, 0, 0, 0.3)
			self.ctx.arc(xrel, yrel, size, 0, 360)
			self.ctx.stroke()
		
		#self.ctx.pop_group_to_source()
		#self.ctx.paint_with_alpha(0.5)
		#self.ctx.paint()
		
	def add_ellipse(self,latmin,latmax,lonmin,lonmax,color="random",fill=True):
		"""Add an ellipse to the context
		"""
		xmin,ymin=self.deg2num_rel(latmax,lonmin)
		xmax,ymax=self.deg2num_rel(latmin,lonmax)

		if xmax-xmin==0:
			xmin-=5
			xmax+=5
		if ymax-ymin==0:
			ymin-=5
			ymax+=5

		xcenter=(xmin+xmax)/2
		ycenter=(ymin+ymax)/2
		self.ctx.push_group()
		self.ctx.curve_to (xcenter, ymin, xmax, ymin, xmax, ycenter)
		self.ctx.curve_to (xmax, ycenter, xmax, ymax, xcenter, ymax)
		self.ctx.curve_to (xcenter, ymax, xmin, ymax, xmin, ycenter)
		self.ctx.curve_to (xmin, ycenter, xmin, ymin, xcenter, ymin)

		r,g,b=self.chose_color(color)
		
		self.ctx.set_source_rgb(r,g,b)
		self.lastcolor=r,g,b
		if fill is True:
			self.ctx.fill()
		else:
			self.ctx.set_line_width(1)
		self.ctx.stroke()
		self.ctx.pop_group_to_source()
		self.ctx.paint_with_alpha(0.5)
		
	def add_line(self,startlat,stoplat,startlon,stoplon,color="random"):
		"""Add a line to the context
		"""
		xstart,ystart=self.deg2num_rel(startlat,startlon)
		xstop,ystop=self.deg2num_rel(stoplat,stoplon)
		
		r,g,b=self.chose_color(color)

		self.ctx.push_group()
		self.ctx.set_source_rgb(r,g,b)
		self.ctx.set_line_width(1)
		self.ctx.move_to(xstart,ystart)
		self.ctx.line_to(xstop,ystop)
		self.ctx.stroke()
		self.ctx.pop_group_to_source()
		self.ctx.paint_with_alpha(0.5)
		
	def add_crosshair(self,lat,lon):
		"""Add a crosshair to the context
		"""
		xrel,yrel=self.deg2num_rel(lat,lon)
		
		self.ctx.push_group()
		self.ctx.set_source_rgb(0,0,255)
		self.ctx.set_line_width(2)
		
		self.ctx.arc(xrel, yrel, 15, 0, 360)
		
		self.ctx.move_to(xrel-20,yrel)
		self.ctx.line_to(xrel+20,yrel)
		self.ctx.move_to(xrel,yrel-20)
		self.ctx.line_to(xrel,yrel+20)
		
		self.ctx.stroke()
		self.ctx.pop_group_to_source()
		self.ctx.paint_with_alpha(1)
		
	def add_branding(self, text, where="center"):
		self.ctx.select_font_face("Arial", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
		self.ctx.set_source_rgba(0, 0, 0, 0.4)
		
		font_size = 10
		if where == "center":
			size = self.width/2
			position_height = 2
		elif where == "top":
			size = self.width/3
			position_height = 10

		while True:
			self.ctx.set_font_size(font_size)
			x_bearing, y_bearing, width, height = self.ctx.text_extents(text)[:4]
			if width > size:
				break
			font_size += 1
		
		self.ctx.move_to((self.width-width)/2, (self.height+height) / position_height)
		self.ctx.show_text(text)
		self.ctx.stroke()
		
	def add_text_footer(self, text, align="left"):
		self.ctx.select_font_face("Arial", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
		self.ctx.set_source_rgba(0, 0, 0, 1)
		self.ctx.set_font_size(14)
		
		x_bearing, y_bearing, width, height = self.ctx.text_extents(text)[:4]
		
		if align == "left":
			self.ctx.move_to(10, self.height-10)
		else:
			self.ctx.move_to(self.width-width-10, self.height-10)
		self.ctx.show_text(text)
		self.ctx.stroke()
	
	def deg2num(self,lat_deg, lon_deg, zoom):
		"""lon/lat to tile numbers 
		"""
		lat_rad = lat_deg * math.pi / 180.0
		n = 2.0 ** zoom
		xtile = (lon_deg + 180.0) / 360.0 * n
		ytile = (1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n
		return(xtile, ytile)
		
	def deg2num_rel(self, lat_deg, lon_deg):
		"""Returns the position in the context
		"""
		x, y = self.deg2num(lat_deg,lon_deg, self.zoom)
		xrel = int((x - self.xmin) * 256)
		yrel = int((y - self.ymin) * 256)
		
		return xrel, yrel

	def num2deg(self, xtile, ytile, zoom):
		"""tile numbers to lon/lat
		This returns the NW-corner of the square. 
		Use the function with xtile+1 and/or ytile+1 to get the other corners. 
		With xtile+0.5 & ytile+0.5 it will return the center of the tile. 
		"""
		n = 2.0 ** zoom
		lon_deg = xtile / n * 360.0 - 180.0
		lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
		lat_deg = lat_rad * 180.0 / math.pi
		return(lat_deg, lon_deg)
		
	def test(self):
		"""Test all functions
		"""
		self.setarea_position(50.6,13.7,2,2,15)
		self.activate_threading()
		self.createcontext()
		self.buildmap()
		"""self.add_ellipse(self.lat["min"],self.lat["max"],self.lon["min"],self.lon["max"])
		self.add_ellipse(self.lat["min"],self.lat["max"],self.lon["min"],self.lon["max"],color=(255,0,0),fill=False)
		self.add_ellipse(self.lat["min"],(self.lat["max"]+self.lat["min"])/2,self.lon["min"],self.lon["max"],color=(255,255,0),fill=False)
		self.add_ellipse((self.lat["max"]+self.lat["min"])/2,self.lat["max"],self.lon["min"],self.lon["max"],color=(0,255,0),fill=True)
		self.add_line(self.lat["min"],self.lat["max"],self.lon["min"],self.lon["max"])
		self.add_crosshair((self.lat["max"]*2+self.lat["min"])/3,(self.lon["max"]*2+self.lon["min"])/3)"""
		self.add_arc((self.lat["max"]+self.lat["min"])/2,(self.lon["max"]+self.lon["min"])/2,10,(0,0,255))
		self.add_branding("test123")
		self.saveimage("osmtest.png")

class DownloadThread(Thread):
	def __init__ (self,result):
		Thread.__init__(self)
		self.is_running=False
		self.queue=[]
		self.osm=Openstreetmap()
		self.result=result
	
	def stop(self):
		self.is_running = False
		sys.exit()
	
	def run(self):
		self.is_running=True
		result=False
		while self.is_running is True and len(self.queue)>0:
			zoom=self.queue[0][0]
			x=self.queue[0][1]
			y=self.queue[0][2]
			self.osm.zoom=zoom
			tile=self.osm.gettile(x,y)
			if tile is not False:
				#print "Loaded Tile",zoom,x,y
				result=True
			del self.queue[0]
		if result is True:
			self.result(True)
		self.stop()

def deg2num(lat_deg, lon_deg, zoom):
	"""lon/lat to tile numbers 
	"""
	lat_rad = math.radians(lat_deg)
	n = 2.0 ** zoom
	xtile = (lon_deg + 180.0) / 360.0 * n
	ytile = (1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n
	return(xtile, ytile)

	
if __name__ == "__main__":
	osm=Openstreetmap()
	osm.test()
	
