
import pygame
import sys
import random
from environment import Environment



def main():

	WIDTH, HEIGHT = 200, 200
	WHITE = (255, 255, 255)
	SCALING_FACTOR = 3

	e = Environment(WIDTH, HEIGHT, 100, 30, 100)

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
		cells_arr = e.get_cells()
		for cell in cells_arr:
			screen.set_at((cell.get_x(), cell.get_y()), cell.get_color())




		win.blit(pygame.transform.scale(screen, win.get_rect().size), (0, 0))
		pygame.display.update()
		
	# Quit Pygame
	pygame.quit()
	sys.exit()



if __name__ == '__main__':
	main()