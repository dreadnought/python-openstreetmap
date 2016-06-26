# Author: Patrick Salecker <mail@salecker.org>

class Config:
	def __init__(self):
		self.mysql = {
			'host': "localhost",
			'user': "yourdatabaseuser",
			'pass': "yourdatabasepassword",
			'db':   "yourdatabasename"
			}
		
		self.image_path = "~/maps/"
		self.user_image_path = "~/usermaps/"
		self.tile_image_path = "~/tiles/"

