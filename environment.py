
import random
import numpy as np

from cell import Cell

n_genes = 4
n_inner_neurons = 2

class Environment:

	def __init__(self, x_size, y_size, population, mutation_rate):

		self.x_size = x_size
		self.y_size = y_size
		self.population = population
		self.mutation_rate = mutation_rate

		self.cells = []

		self.grid = np.zeros((x_size, y_size))


		for i in range(population):
			x_i = random.randint(0, self.x_size-1)
			y_i = random.randint(0, self.y_size-1)

			while self.grid[x_i, y_i] != 0:
				x_i = random.randint(0, self.x_size-1)
				y_i = random.randint(0, self.y_size-1)

			self.cells.append(Cell(x_i, y_i, n_genes, n_inner_neurons, i+1, self))
			self.grid[x_i, y_i] = i+1

	def get_x_size(self):
		return self.x_size

	def get_y_size(self):
		return self.y_size

	def get_cells(self):
		return self.cells

	def get_grid(self):
		return self.grid

	def get_next_generation_asexually(self):

		for i in range(len(self.cells)):
			self.cells[i].mutate_genome(self.mutation_rate)
			





