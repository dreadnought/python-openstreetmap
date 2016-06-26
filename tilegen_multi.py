#!/usr/bin/env python
# coding=utf-8
#
# Author: Patrick Salecker <mail@salecker.org>

import MySQLdb
import MySQLdb.cursors
import MySQLdb.converters

import math
import time
import os
import sys
import hashlib
import json

from config import Config
from openstreetmap import Openstreetmap, deg2num

class GenerateZoomLevel:
	def __init__(self, zoomlevel):
		self.config = Config()
		self.datastore = {}
		self.zoomlevel = []
		for zoom in zoomlevel:
			zoom = int(zoom)
			self.zoomlevel.append(zoom)
			self.datastore[zoom] = {}
			self.tile_hashes = {}
		
		self.size = 3
		self.color = [(0, 1, 0), (1, 1, 0), (1, 0, 0), (0, 0, 1)] #green,yellow,red,blue
		
	def dump_db(self):
		converter = MySQLdb.converters.conversions.copy()
		converter[246] = float
		self.mysql = MySQLdb.connect(self.config.mysql['host'], 
			self.config.mysql['user'], 
			self.config.mysql['pass'], 
			self.config.mysql['db'],
			cursorclass = MySQLdb.cursors.SSCursor,
			conv = converter,
			) 
		self.cursor = self.mysql.cursor()
		query = """SELECT lat,lon,color FROM networks 
			WHERE lat!=0 and lon!=0"""
		
		limit = 500000
		count = 0
		print "start"

		while True:
			start_time = time.time()
			num = self.cursor.execute("%s LIMIT %s,%s" %(query, count*limit, limit))
			num = 0
			count += 1
			print count, num
			query_time = time.time()
			print round(query_time - start_time, 2),
			
			for lat, lon, color in self.cursor:
				num += 1
				if color = "red":
					color = 2
				elif crypt == "yellow":
					color = 1
				else:
					color = 0
				for zoom in self.zoomlevel:
					try:
						x, y = deg2num(lat, lon, zoom)
					except ValueError:
						continue
						
					if zoom >= 13:
						color = 3
					
					x_int = int(x)
					y_int = int(y)
					x_rel = int((x - x_int) * 256)
					y_rel = int((y - y_int) * 256)
					
					row = "%s:%s:%s" % (x_rel, y_rel, color)
					
					if x_rel + self.size >= 256:
						self.add_to_datastore(zoom, x_int + 1, y_int, "%s:%s:%s" % (x_rel-256, y_rel, color))
					elif x_rel - self.size < 0:
						self.add_to_datastore(zoom, x_int - 1, y_int, "%s:%s:%s" % (x_rel+256, y_rel, color))
						
					if y_rel + self.size >= 256:
						self.add_to_datastore(zoom, x_int, y_int + 1, "%s:%s:%s" % (x_rel, y_rel-256, color))
					elif y_rel - self.size < 0:
						self.add_to_datastore(zoom, x_int, y_int - 1, "%s:%s:%s" % (x_rel, y_rel-256, color))
					
					self.add_to_datastore(zoom, x_int, y_int, row)
				
			#print len(self.datastore)
			print round(time.time() - query_time, 2)
			#break
			if num < limit:
				break
				
		tiles = 0
		for x in self.datastore:
			tiles += len(self.datastore[x])
		print "Tiles", tiles
		
		self.cursor.close()
		self.mysql.close()
		
	def add_to_datastore(self, zoom, x_int, y_int, row):
		try:
			self.datastore[zoom][x_int][y_int].append(row)
		except KeyError:
			try:
				self.datastore[zoom][x_int][y_int] = [row, ]
			except KeyError:
				self.datastore[zoom][x_int] = {y_int: [row, ]}
				
	def generate_tiles(self, zoom):
		print "read"
		old_hashes = self.load_tile_hashes(zoom)
		self.tile_hashes = {}
		#start_time = time.time()
		for x_int in self.datastore[zoom].keys():
			if x_int < 0:
				continue
			for y_int in self.datastore[zoom][x_int].keys():
				old_hash = None
				hash_key = "%s %s" % (x_int, y_int)
				if hash_key in old_hashes:
					old_hash = old_hashes[hash_key]
				self.generate_tile(zoom, x_int, y_int, old_hash)
		self.save_tile_hashes(zoom)
			
	def generate_tile(self, zoom, x_int, y_int, old_hash):
		rows = self.datastore[zoom][x_int][y_int]
		tile_hash = hashlib.sha1()
		tile_hash.update(json.dumps(rows))
		#print tile_hash.hexdigest()
		tile_hash_str = tile_hash.hexdigest()
		self.tile_hashes["%s %s" %(x_int, y_int)] = tile_hash_str
		
		if tile_hash_str == old_hash:
			return
		osm = Openstreetmap()
		osm.draw_no_dupes()
		osm.setarea(x_int, x_int, y_int, y_int, zoom)
		osm.createcontext()
		
		for row in rows:
			x_rel, y_rel, color = row.split(":")
			osm.add_arc_xy(int(x_rel), int(y_rel), self.size, self.color[int(color)], True, True)
		
		path = "%s%s/%s" %(self.config.tile_image_path, zoom, x_int)
		if not os.path.isdir(path):
			os.makedirs(path)
		#print path, "%s/%s.png" %(path, y_int)
		osm.saveimage("%s/%s.png" %(path, y_int))
		
	def save_tile_hashes(self, zoom):
		f = open("%s%s/hashes.txt" % (self.config.tile_image_path, zoom), "w")
		for tile_hash in self.tile_hashes:
			f.write("%s;%s\n" %(tile_hash, self.tile_hashes[tile_hash]))
			
	def load_tile_hashes(self, zoom):
		path = "%s%s/hashes.txt" % (self.config.tile_image_path, zoom)
		if not os.path.isfile(path):
			return {}
		f = open(path, "r")
		old_hashes = {}
		for line in f.readlines():
			key, value = line.split(";")
			old_hashes[key] = value.strip()
		return old_hashes

def main():
	import resource
	gen = GenerateZoomLevel(sys.argv[1].split(","))
	start_time = time.time()
	gen.dump_db()
	print "Database",round(time.time() - start_time, 2)
	print resource.getrusage(resource.RUSAGE_SELF)
	for zoom in gen.zoomlevel:
		print repr(zoom)
		zoom = int(zoom)
		gen_time = time.time()
		gen.generate_tiles(zoom)
		print "Generate", zoom,round(time.time() - gen_time, 2)
	
	print "Total",round(time.time() - start_time, 2)
	print resource.getrusage(resource.RUSAGE_SELF)

main()
