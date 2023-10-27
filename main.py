
import pygame
import sys
import random
from environment import Environment



def main():

	WIDTH, HEIGHT = 200, 200
	WHITE = (255, 255, 255)
	SCALING_FACTOR = 3

	STEPS_PER_GENERATION = 30
	N_GENERATIONS = 1
	POPULATION = 10

	environment = Environment(WIDTH, HEIGHT, POPULATION)

	pygame.init()

	screen = pygame.display.set_mode((WIDTH, HEIGHT))
	pygame.display.set_caption("Evolution")
	win = pygame.display.set_mode((WIDTH*SCALING_FACTOR, HEIGHT*SCALING_FACTOR))

	screen = pygame.Surface((WIDTH, HEIGHT))


	running = True

	while running:
		for event in pygame.event.get():
			if event.type == pygame.QUIT:
				running = False

		screen.fill(WHITE)


		# Draw Cells
		cells_arr = environment.get_cells()
		for cell in cells_arr:
			screen.set_at((cell.get_x(), cell.get_y()), cell.get_color())




		### Generational Loop ###

		for generation in range(N_GENERATIONS):



			### Step Loop ###

			for step in range(STEPS_PER_GENERATION):

				# Get decisions from cells
				cells_arr = environment.get_cells()

				print(cells_arr[0])

				for i in range(len(cells_arr)):

					# Get cells
					cell = cells_arr[i]

					# Update Sensory Neurons
					cell.activate_sensory_neurons()
					cell.think()

					# Get Decision and execute
					decision = cell.get_decision()
					cell.execute_decision(decision)

					# Grow
					cell.age_up()

				# Update board
				screen.fill(WHITE)
				for cell in cells_arr:
					screen.set_at((cell.get_x(), cell.get_y()), cell.get_color())

				pygame.time.wait(5)

		win.blit(pygame.transform.scale(screen, win.get_rect().size), (0, 0))
		pygame.display.update()

	# Quit Pygame
	pygame.quit()
	sys.exit()



if __name__ == '__main__':
	main()