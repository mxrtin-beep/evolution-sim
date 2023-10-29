
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
			
			x_i, y_i = self.find_free_position()
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

	def get_population(self):
		return len(self.cells)

	def find_free_position(self):

		x_i = random.randint(0, self.x_size-1)
		y_i = random.randint(0, self.y_size-1)

		while self.grid[x_i, y_i] != 0:
			x_i = random.randint(0, self.x_size-1)
			y_i = random.randint(0, self.y_size-1)

		return x_i, y_i


	def mutate_all_cells(self):

		for i in range(len(self.cells)):
			cell = self.cells[i]
			self.cells[i].mutate_genome(self.mutation_rate)


	def randomly_move_all_cells(self):

		for i in range(len(self.cells)):
			cell = self.cells[i]
			self.grid[cell.get_x(), cell.get_y()] = 0
			x_i, y_i = self.find_free_position()
			cell.set_position(x_i, y_i)
			self.grid[x_i, y_i] = cell.get_id()
			cell.randomize_direction()

	def fix_cell_ids(self):

		for i in range(len(self.cells)):
			self.cells[i].set_id(i+1)

	def fix_grid(self):

		self.grid = np.zeros((self.x_size, self.y_size))
		for i in range(len(self.cells)):
			cell = self.cells[i]
			self.grid[cell.get_x(), cell.get_y()] = i+1

	def get_next_generation_asexually(self, new_population):

		self.mutate_all_cells()
		self.randomly_move_all_cells()
		
		population_change = int(new_population) - len(self.cells)

		# If population is decreasing, remove cells
		while population_change < 0:
			removed_cell = self.cells.pop(random.randint(0, len(self.cells) - 1))
			self.grid[removed_cell.get_x(), removed_cell.get_y()] = 0
			population_change += 1

		# If population is increasing, add cells
		if population_change > 0:

			for i in range(population_change):
				cell_idx = i%len(self.cells)
				new_genome = self.cells[cell_idx].get_mutated_genome(self.mutation_rate)
				
				x_i, y_i = self.find_free_position()
				new_cell = Cell(x_i, y_i, n_genes, n_inner_neurons, len(self.cells), self)
				new_cell.set_genome(new_genome)
				self.cells.append(new_cell)
				self.grid[x_i, y_i] = len(self.cells)

		self.fix_cell_ids()
		self.fix_grid()


	# Kill certain cells
	def enact_selection_pressure(self):

		current_population = self.get_population()
		surviving_population = current_population

		new_cell_arr = []
		for i in range(len(self.cells)):
			cell = self.cells[i]

			death_condition = (cell.get_x() > 3 and cell.get_y() > 3 and cell.get_x() < 197 and cell.get_y() < 197)
			#death_condition = False
			#death_condition = cell.get_x() > 100
			# Kill all cells on the right side of the board
			if not death_condition:
				new_cell_arr.append(cell)
			else:
				surviving_population -= 1

		self.cells = new_cell_arr

		self.fix_cell_ids()
		self.fix_grid()

		percent_surviving = round(surviving_population / current_population * 100, 2)
		return percent_surviving



	def calculate_genetic_diversity(self):

		n_possible_genes = self.get_population()*n_genes
		unique_genes = []

		for cell in self.cells:
			for gene in cell.get_genome():
				if gene not in unique_genes:
					unique_genes.append(gene)

		return float(len(unique_genes) - n_genes) / float(n_possible_genes) * 100


