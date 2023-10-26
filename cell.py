
import random
import secrets
from brain import Brain


class Cell:

	

	def __init__(self, x, y, n_genes, n_inner_neurons, id_number):

		dirs = [-1, 1]

		self.x_pos = x
		self.y_pos = y

		self.x_dir = dirs[random.randint(0, 1)]
		self.y_dir = dirs[random.randint(0, 1)]

		self.genome = []

		for i in range(n_genes):
			self.genome.append(secrets.token_hex(4))	# 4 genes by 4 bytes = 16 bytes, 128 bits

		self.brain = Brain(self.genome, n_inner_neurons)

		self.id_number = id_number

	def get_x(self):
		return self.x_pos

	def get_y(self):
		return self.y_pos

	def get_id(self):
		return self.id_number

	def get_color(self):

		gene_max = int('ffffffff', 16)
		color_max = 255

		return (
			int(int(self.genome[0], 16)/gene_max*color_max), 
			int(int(self.genome[1], 16)/gene_max*color_max),
			int(int(self.genome[2], 16)/gene_max*color_max),
			)

	def get_decision(self):
		return 0