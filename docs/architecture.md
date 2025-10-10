# Arquitectura de la aplicación

Esta es una **aplicación de escritorio** construida con Tkinter y ttkbootstrap.
El código se organiza siguiendo un esquema estilo MVC:

- `app/controllers`: contiene los controladores que orquestan el flujo entre
  la interfaz y los servicios.
- `app/services`: encapsula la lógica de negocio reutilizable (historiales,
  interacción con Chrome y utilidades de nombres).
- `app/daos`: se encarga del acceso a los datos, actualmente mediante archivos
  JSON que funcionan como historiales locales.
- `app/dtos`: define los objetos de transferencia que viajan entre capas.
- `app/views`: concentra las vistas de la interfaz gráfica.

El punto de entrada de la aplicación es `main.py`, que inicializa la interfaz
principal ubicada en `app/views/main_view.py`.
