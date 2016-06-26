#!/usr/bin/env python
# coding=utf-8
#
# Author: Patrick Salecker <mail@salecker.org>

from openstreetmap import Openstreetmap
import MySQLdb
import time
from PIL import Image
import locale
import sys
import urllib;
import math

from config import Config

class NetworkMap:
	def __init__(self):
		self.config = Config()
		map_name = "Test"
		self.mysql = MySQLdb.connect(self.config.mysql['host'], 
			self.config.mysql['user'], 
			self.config.mysql['pass'], 
			self.config.mysql['db']) 
		self.cursor = self.mysql.cursor(MySQLdb.cursors.DictCursor)
		self.blacklist = ()
		
	def update_maps(self, limit, user=False):
		if user:
			num = self.cursor.execute("""SELECT 
				username AS name,
				userid AS id,
				map_xmin AS xmin,
				map_xmax AS xmax,
				map_ymin AS ymin,
				map_ymax AS ymax,
				map_zoom AS zoom,
				map_auto,
				username
				FROM user WHERE map_request=1 ORDER BY map_update ASC LIMIT %s""" % limit)
		else:
			num = self.cursor.execute("SELECT * FROM maps WHERE pub=1 AND name NOT IN %s ORDER BY last_update ASC LIMIT %s" % (repr(self.blacklist), limit))
		position = 1
		for row in  self.cursor.fetchall():
			#print "%s." % position
			self.cursor = self.mysql.cursor(MySQLdb.cursors.DictCursor)
			try:
				self.create_map(row, user)
			except:
				print sys.exc_info()
			position += 1
			#print "pause"
			#time.sleep(10)
		
	def map_by_name(self, name):
		num = self.cursor.execute("SELECT * FROM maps WHERE name='%s' LIMIT 1" % unicode(name, "utf-8"))
		row = self.cursor.fetchone()
		if num != 0:
			self.create_map(row)
		else:
			print "not found"
		
	def create_map(self, row, user=False):
		name = row["name"]
		if user:
			file_name = "%s" % row["id"]
			file_path = self.config.user_image_path
			if row["map_auto"] == 1:
				row = self.usermap_range(row)
		else:
			file_name = name.lower()
			file_name = file_name.replace(" ", "_")
			file_name = file_name.replace("\xe4", "ae")
			file_name = file_name.replace("\xc4", "ae")
			file_name = file_name.replace("\xf6", "oe")
			file_name = file_name.replace("\xd6", "oe")
			file_name = file_name.replace("\xfc", "ue")
			file_name = file_name.replace("\xdc", "ue")
			file_name = file_name.replace("\xdf", "ss")
			file_path = self.config.image_path
		#print "filename", file_name,
		
		self.osm = Openstreetmap()
		self.osm.draw_no_dupes()
		self.osm.setarea(row["xmin"],row["xmax"],row["ymin"],row["ymax"],row["zoom"])
		self.osm.createcontext()
		self.osm.buildmap()
		
		start = time.time()
		self.cursor = self.mysql.cursor()
		query = """SELECT lat,lon,color FROM networks 
			WHERE lat BETWEEN %s AND %s AND lon BETWEEN %s AND %s and lat!=0 and lon!=0 %s
			""" %(
				self.osm.lat["min"], self.osm.lat["max"],
				self.osm.lon["min"], self.osm.lon["max"],
				"AND userid=%s" % row["id"] if user else "AND userid NOT IN (70884)"
				)
		
		limit = 500000
		count = 0
		networks = 0
		stop = False
		while True:
			if name in self.blacklist:
				num = self.cursor.execute("%s LIMIT %s,%s" %(query, count*limit, limit))
			else:
				num = self.cursor.execute(query)
				stop = True
			count += 1
			networks += num
			#print num,
			
			for x in range(num):
				network = self.cursor.fetchone()
				if "red" in network[2]:
					color = (1, 0, 0)
				elif network[2] == "yellow":
					color = (1, 1, 0)
				else:
					color = (0, 1 ,0)
				
				self.osm.add_arc(float(network[0]), float(network[1]), 3, color, True, True)
			
			if num == 0 or num < limit or stop:
				break
		
		now = time.strftime("%d.%m.%Y %H:%M")
		locale.setlocale(locale.LC_ALL, '')
		num_aps = locale.format("%0.f", networks, True)
		
		if user:
			print row["name"].decode("iso-8859-1")
			self.osm.add_branding("%s @ example.com" % row["name"].decode("iso-8859-1"), "top")
		else:
			self.osm.add_branding("example.com")
		self.osm.add_text_footer("Stand %s, %s APs" % (now, num_aps), "right")
		self.osm.add_text_footer("Kartenmaterial (c) OpenStreetMap und Mitwirkende, CC-BY-SA", "left")
		
		self.osm.saveimage("%s%s.png" % (file_path, file_name))
		
		size =  240,240
		img = Image.open(file_path + file_name + ".png")
		img.thumbnail(size, Image.ANTIALIAS)
		img.save(file_path + file_name + "_t.png", "PNG")
		
		creation_time = round(time.time() - start, 2)
		if user:
			self.cursor.execute("UPDATE user SET map_update=%s, map_creation_time=%s, map_request=0 WHERE userid='%s'" % (int(time.time()), creation_time, row["id"]))
		else:
			self.cursor.execute("UPDATE maps SET last_update=%s, networks=%s, creation_time=%s WHERE id='%s'" % (int(time.time()), num, creation_time, row["id"]))
		#print creation_time
		
	def user_by_name(self, name):
		num = self.cursor.execute("""SELECT 
			username AS name,
			userid AS id,
			map_xmin AS xmin,
			map_xmax AS xmax,
			map_ymin AS ymin,
			map_ymax AS ymax,
			map_zoom AS zoom,
			map_auto,
			username
			FROM user WHERE username='%s' LIMIT 1""" % unicode(name, "utf-8"))
		row = self.cursor.fetchone()
		if num != 0:
			self.create_map(row, user=True)
		else:
			print "not found"
	
	def usermap_range(self, row):
		num = self.cursor.execute("""SELECT 
			userid,
			COUNT(*) as count,
			MAX(lat) AS latmax,
			MIN(lat) AS latmin,
			MAX(lon) AS lonmax,
			MIN(lon) AS lonmin 
			FROM networks 
			WHERE userid=%s AND
			lat!=0 AND lon!=0 AND 
			lat BETWEEN -90 AND 90 AND
			lon BETWEEN -180 AND 180
			GROUP BY userid""" % (row["id"], ))
		
		if num != 1:
			return row
		
		user = self.cursor.fetchone()
		
		zoom = 16
		calcmax = math.log(math.tan(math.radians(85.0511))+(1/math.cos(math.radians(85.0511))))
		
		while True:
			zoom_value = 2 ** zoom
			calcmaxzoom = 2 * calcmax / zoom_value;
			
			row["xmin"] = int(math.floor(((user['lonmin'] + 180) / 360) * zoom_value));
			row["xmax"] = int(math.ceil(((user['lonmax'] + 180) / 360) * zoom_value - 1));
			
			yminrad = math.radians(user['latmax']);
			row["ymin"] = int(math.floor((calcmax-math.log(math.tan(yminrad)+(1/math.cos(yminrad))))/calcmaxzoom))
			ymaxrad=math.radians(user['latmin']);
			row["ymax"] = int(math.ceil((calcmax-math.log(math.tan(ymaxrad)+(1/math.cos(ymaxrad))))/calcmaxzoom-1))
			if (row["xmax"] - row["xmin"]) < 7 and (row["ymax"] - row["ymin"]) < 7:
				row["zoom"] = zoom
				break
			else:
				zoom -= 1;
		
		return row

network_map = NetworkMap()
if sys.argv[1] == "map":
	if sys.argv[2] == "update":
		network_map.update_maps(sys.argv[3])
	elif sys.argv[2] == "name":
		network_map.map_by_name(sys.argv[3])
elif sys.argv[1] == "user":
	if sys.argv[2] == "update":
		network_map.update_maps(sys.argv[3], user=True)
	elif sys.argv[2] == "name":
		network_map.user_by_name(sys.argv[3])

