# Install script for directory: C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK

# Set the install prefix
if(NOT DEFINED CMAKE_INSTALL_PREFIX)
  set(CMAKE_INSTALL_PREFIX "C:/Program Files/DirectXTK")
endif()
string(REGEX REPLACE "/$" "" CMAKE_INSTALL_PREFIX "${CMAKE_INSTALL_PREFIX}")

# Set the install configuration name.
if(NOT DEFINED CMAKE_INSTALL_CONFIG_NAME)
  if(BUILD_TYPE)
    string(REGEX REPLACE "^[^A-Za-z0-9_]+" ""
           CMAKE_INSTALL_CONFIG_NAME "${BUILD_TYPE}")
  else()
    set(CMAKE_INSTALL_CONFIG_NAME "Release")
  endif()
  message(STATUS "Install configuration: \"${CMAKE_INSTALL_CONFIG_NAME}\"")
endif()

# Set the component getting installed.
if(NOT CMAKE_INSTALL_COMPONENT)
  if(COMPONENT)
    message(STATUS "Install component: \"${COMPONENT}\"")
    set(CMAKE_INSTALL_COMPONENT "${COMPONENT}")
  else()
    set(CMAKE_INSTALL_COMPONENT)
  endif()
endif()

# Is this installation the result of a crosscompile?
if(NOT DEFINED CMAKE_CROSSCOMPILING)
  set(CMAKE_CROSSCOMPILING "FALSE")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  if(CMAKE_INSTALL_CONFIG_NAME MATCHES "^([Dd][Ee][Bb][Uu][Gg])$")
    file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib" TYPE STATIC_LIBRARY FILES "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/cmake_build_x64/bin/CMake/Debug/DirectXTK.lib")
  elseif(CMAKE_INSTALL_CONFIG_NAME MATCHES "^([Rr][Ee][Ll][Ee][Aa][Ss][Ee])$")
    file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib" TYPE STATIC_LIBRARY FILES "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/cmake_build_x64/bin/CMake/Release/DirectXTK.lib")
  elseif(CMAKE_INSTALL_CONFIG_NAME MATCHES "^([Mm][Ii][Nn][Ss][Ii][Zz][Ee][Rr][Ee][Ll])$")
    file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib" TYPE STATIC_LIBRARY FILES "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/cmake_build_x64/bin/CMake/MinSizeRel/DirectXTK.lib")
  elseif(CMAKE_INSTALL_CONFIG_NAME MATCHES "^([Rr][Ee][Ll][Ww][Ii][Tt][Hh][Dd][Ee][Bb][Ii][Nn][Ff][Oo])$")
    file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib" TYPE STATIC_LIBRARY FILES "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/cmake_build_x64/bin/CMake/RelWithDebInfo/DirectXTK.lib")
  endif()
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  if(EXISTS "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/share/directxtk/DirectXTK-targets.cmake")
    file(DIFFERENT _cmake_export_file_changed FILES
         "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/share/directxtk/DirectXTK-targets.cmake"
         "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/cmake_build_x64/CMakeFiles/Export/a11a99d19d8d3c8432b0fa94ef825414/DirectXTK-targets.cmake")
    if(_cmake_export_file_changed)
      file(GLOB _cmake_old_config_files "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/share/directxtk/DirectXTK-targets-*.cmake")
      if(_cmake_old_config_files)
        string(REPLACE ";" ", " _cmake_old_config_files_text "${_cmake_old_config_files}")
        message(STATUS "Old export file \"$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/share/directxtk/DirectXTK-targets.cmake\" will be replaced.  Removing files [${_cmake_old_config_files_text}].")
        unset(_cmake_old_config_files_text)
        file(REMOVE ${_cmake_old_config_files})
      endif()
      unset(_cmake_old_config_files)
    endif()
    unset(_cmake_export_file_changed)
  endif()
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/share/directxtk" TYPE FILE FILES "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/cmake_build_x64/CMakeFiles/Export/a11a99d19d8d3c8432b0fa94ef825414/DirectXTK-targets.cmake")
  if(CMAKE_INSTALL_CONFIG_NAME MATCHES "^([Dd][Ee][Bb][Uu][Gg])$")
    file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/share/directxtk" TYPE FILE FILES "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/cmake_build_x64/CMakeFiles/Export/a11a99d19d8d3c8432b0fa94ef825414/DirectXTK-targets-debug.cmake")
  endif()
  if(CMAKE_INSTALL_CONFIG_NAME MATCHES "^([Mm][Ii][Nn][Ss][Ii][Zz][Ee][Rr][Ee][Ll])$")
    file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/share/directxtk" TYPE FILE FILES "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/cmake_build_x64/CMakeFiles/Export/a11a99d19d8d3c8432b0fa94ef825414/DirectXTK-targets-minsizerel.cmake")
  endif()
  if(CMAKE_INSTALL_CONFIG_NAME MATCHES "^([Rr][Ee][Ll][Ww][Ii][Tt][Hh][Dd][Ee][Bb][Ii][Nn][Ff][Oo])$")
    file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/share/directxtk" TYPE FILE FILES "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/cmake_build_x64/CMakeFiles/Export/a11a99d19d8d3c8432b0fa94ef825414/DirectXTK-targets-relwithdebinfo.cmake")
  endif()
  if(CMAKE_INSTALL_CONFIG_NAME MATCHES "^([Rr][Ee][Ll][Ee][Aa][Ss][Ee])$")
    file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/share/directxtk" TYPE FILE FILES "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/cmake_build_x64/CMakeFiles/Export/a11a99d19d8d3c8432b0fa94ef825414/DirectXTK-targets-release.cmake")
  endif()
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/include/directxtk" TYPE FILE FILES
    "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/Inc/BufferHelpers.h"
    "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/Inc/CommonStates.h"
    "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/Inc/DDSTextureLoader.h"
    "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/Inc/DirectXHelpers.h"
    "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/Inc/Effects.h"
    "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/Inc/GeometricPrimitive.h"
    "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/Inc/GraphicsMemory.h"
    "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/Inc/Model.h"
    "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/Inc/PostProcess.h"
    "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/Inc/PrimitiveBatch.h"
    "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/Inc/ScreenGrab.h"
    "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/Inc/SpriteBatch.h"
    "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/Inc/SpriteFont.h"
    "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/Inc/VertexTypes.h"
    "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/Inc/WICTextureLoader.h"
    "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/Inc/GamePad.h"
    "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/Inc/Keyboard.h"
    "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/Inc/Mouse.h"
    "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/Inc/SimpleMath.h"
    "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/Inc/SimpleMath.inl"
    )
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/share/directxtk" TYPE FILE FILES
    "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/cmake_build_x64/directxtk-config.cmake"
    "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/cmake_build_x64/directxtk-config-version.cmake"
    )
endif()

if(CMAKE_INSTALL_COMPONENT)
  set(CMAKE_INSTALL_MANIFEST "install_manifest_${CMAKE_INSTALL_COMPONENT}.txt")
else()
  set(CMAKE_INSTALL_MANIFEST "install_manifest.txt")
endif()

string(REPLACE ";" "\n" CMAKE_INSTALL_MANIFEST_CONTENT
       "${CMAKE_INSTALL_MANIFEST_FILES}")
file(WRITE "C:/Users/HongM/Code Projects/live2d/cubism/Samples/D3D11/thirdParty/DirectXTK/cmake_build_x64/${CMAKE_INSTALL_MANIFEST}"
     "${CMAKE_INSTALL_MANIFEST_CONTENT}")
